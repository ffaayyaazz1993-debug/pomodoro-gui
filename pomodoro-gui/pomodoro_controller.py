"""
pomodoro_controller.py — shared state + timer engine for the pomodoro GUI.

Each tab (TodoTab, MindmapTab, etc.) receives a reference to the controller
and calls its methods instead of owning shared state directly. This lets the
tabs live in separate files without reaching into the App's internals.
"""
import os
import queue
import threading
import time
from datetime import datetime

from pomodoro_common import (
    DATA_FILE,
    STATUS_FILE,
    LOG_FILE,
    Q1, Q2, Q3, Q4,
    PQ_LABEL,
    load,
    save,
    get_current_project,
    all_todos,
    fire_sound,
    toast,
    notify,
    TimerRunner,
)


class PomodoroController:
    """Holds shared state and timer engine for all tabs."""

    def __init__(self, master, nb, sound_on, auto_chain, dark_mode, project_var):
        self.master = master
        self.nb = nb
        self.sound_on = sound_on
        self.auto_chain = auto_chain
        self.dark_mode = dark_mode
        self.project_var = project_var

        # per-task timers: task_id -> {'runner':..., 'thread':..., 'q':..., 'poll':..., 'card':...}
        self.timers = {}
        self._task_cards = {}

        # callbacks registered by tabs (e.g. TodoTab refreshes on timer events)
        self._on_timer_event = None

    # ------------------------------------------------------------------
    # Timer event subscription
    # ------------------------------------------------------------------
    def on_timer_event(self, callback):
        """Register a callback for timer start/finish/cancel events."""
        self._on_timer_event = callback

    def _notify_timer_event(self):
        if self._on_timer_event:
            self._on_timer_event()

    # ------------------------------------------------------------------
    # Project helpers
    # ------------------------------------------------------------------
    def current_project(self):
        data = load()
        return get_current_project(data)

    def refresh_projects(self):
        """Refresh project dropdown values. Called by tabs that show projects."""
        data = load()
        names = [p['name'] for p in data['projects']]
        current = data.get('current_project', 'default')
        current_name = ''
        for p in data['projects']:
            if p['id'] == current:
                current_name = p['name']
                break
        return names, current_name

    def set_project(self, name):
        data = load()
        for p in data['projects']:
            if p['name'] == name:
                data['current_project'] = p['id']
                break
        save(data)

    def add_project(self, name):
        import uuid
        data = load()
        pid = str(uuid.uuid4())[:8]
        data['projects'].append({
            'id': pid,
            'name': name,
            'todos': [],
            'schedules': []
        })
        data['current_project'] = pid
        save(data)

    def remove_project(self, pid):
        data = load()
        if len(data['projects']) <= 1:
            return False
        # remove timers for tasks in this project
        for t in data['projects']:
            if t['id'] == pid:
                for todo in t.get('todos', []):
                    tid = todo['id']
                    if tid in self.timers:
                        self._kill_timer(tid)
                break
        data['projects'] = [p for p in data['projects'] if p['id'] != pid]
        data['current_project'] = data['projects'][0]['id']
        save(data)
        return True

    # ------------------------------------------------------------------
    # Timer engine
    # ------------------------------------------------------------------
    def timer_for_task(self, task_id):
        return self.timers.get(task_id)

    def start_timer_for(self, task_id, minutes):
        if task_id in self.timers:
            old = self.timers[task_id]
            old['runner'].cancel()
            if old['thread'] and old['thread'].is_alive():
                old['thread'].join(timeout=2)
            if old['poll']:
                try:
                    self.master.after_cancel(old['poll'])
                except Exception:
                    pass
            old_card = self._task_cards.get(task_id)
            sound = old_card['sound_var'].get() if old_card else self.sound_on.get()
            self._remove_card(task_id)
        else:
            sound = self.sound_on.get()
        q = queue.Queue()
        runner = TimerRunner(task_id, minutes, sound)
        runner.start()
        # rebuild the card for this task with new timer state
        data = load()
        todo = None
        for t in all_todos(data):
            if t['id'] == task_id:
                todo = t
                break
        if todo:
            self._build_task_card(todo)
        self.timers[task_id] = {'runner': runner, 'thread': None,
                                 'q': q, 'poll': None, 'card': None}
        self._write_status('pomodoro: %dm (%s) | running' % (minutes, task_id))
        self._log('START', minutes, task_id)
        poll_id = self.master.after(200, lambda: self._timer_poll(task_id))
        self.timers[task_id]['poll'] = poll_id
        thr = threading.Thread(target=lambda: self._timer_thread(task_id), daemon=True)
        self.timers[task_id]['thread'] = thr
        thr.start()
        self._notify_timer_event()

    def _build_task_card(self, todo):
        """Placeholder — overridden by TodoTab to build actual card widgets."""
        pass

    def _remove_card(self, task_id):
        """Placeholder — overridden by TodoTab to destroy actual card widgets."""
        card = self._task_cards.pop(task_id, None)
        if card and hasattr(card, 'destroy'):
            card.destroy()

    def card_stop(self, task_id):
        self._kill_timer(task_id)

    def card_pause(self, task_id):
        entry = self.timers.get(task_id)
        if not entry:
            return
        r = entry['runner']
        if r.paused:
            r.resume()
        else:
            r.pause()

    def card_skip(self, task_id):
        data = load()
        for t in all_todos(data):
            if t['id'] == task_id:
                t['pomodoros'] = t.get('pomodoros', 0) + 1
                break
        save(data)
        self._notify_timer_event()

    def _timer_thread(self, task_id):
        entry = self.timers.get(task_id)
        if not entry:
            return
        runner = entry['runner']
        q = entry['q']
        while runner.is_alive() and not runner.canceled:
            elapsed, total, done, paused = runner.tick()
            try:
                q.put((elapsed, total, done, paused))
            except Exception:
                pass
            if done:
                break
            time.sleep(0.5)

    def _timer_poll(self, task_id):
        entry = self.timers.get(task_id)
        if not entry:
            return
        q = entry['q']
        try:
            while True:
                elapsed, total, done, paused = q.get_nowait()
                self._update_card(task_id, elapsed, total, done, paused)
                if done:
                    self._timer_finished(task_id)
                    return
        except queue.Empty:
            pass
        entry['poll'] = self.master.after(200, lambda: self._timer_poll(task_id))

    def _update_card(self, task_id, elapsed, total, done, paused):
        """Placeholder — overridden by TodoTab to update actual card widgets."""
        pass

    def _timer_finished(self, task_id):
        entry = self.timers.get(task_id)
        if not entry:
            return
        runner = entry['runner']
        self._write_status('pomodoro: %dm (%s) | DONE' % (runner.minutes, task_id))
        self._log('DONE', runner.minutes, task_id)
        # increment pomodoros for that task in-place
        data = load()
        for t in all_todos(data):
            if t['id'] == task_id:
                t['pomodoros'] = t.get('pomodoros', 0) + 1
                t['last_done'] = datetime.now().isoformat()
                break
        save(data)
        if runner.sound_on:
            fire_sound()
        toast('Pomodoro Done', '%s — %d minutes elapsed.' % (task_id, runner.minutes))
        # remove card, then timer entry
        self._remove_card(task_id)
        del self.timers[task_id]
        # auto-chain: start the next open todo if enabled
        if self.auto_chain.get():
            next_tid = self._find_next_open_todo()
            if next_tid and next_tid not in self.timers:
                self.start_timer_for(next_tid, 25)
        self._notify_timer_event()

    def _find_next_open_todo(self):
        project = self.current_project()
        if not project:
            return None
        todos = [t for t in project.get('todos', []) if not t.get('done')]
        if not todos:
            return None
        def key(t):
            p = t.get('priority')
            pnum = p if p in (Q1, Q2, Q3, Q4) else 99
            try:
                ts = time.mktime(time.strptime(t['created'], '%Y-%m-%dT%H:%M:%S'))
            except Exception:
                ts = 0.0
            return (pnum, -ts)
        todos_sorted = sorted(todos, key=key)
        return todos_sorted[0]['id']

    def kill_timer(self, task_id):
        self._kill_timer(task_id)

    def _kill_timer(self, task_id):
        entry = self.timers.pop(task_id, None)
        if not entry:
            return
        entry['runner'].cancel()
        if entry['thread'] and entry['thread'].is_alive():
            entry['thread'].join(timeout=2)
        if entry['poll']:
            try:
                self.master.after_cancel(entry['poll'])
            except Exception:
                pass
        self._remove_card(task_id)
        self._notify_timer_event()

    def timer_state_text(self, task_id):
        if task_id not in self.timers:
            return ''
        r = self.timers[task_id]['runner']
        if r.done and not r.paused:
            return 'done'
        if r.paused:
            return 'paused'
        return 'running'

    def _write_status(self, msg):
        try:
            with open(STATUS_FILE, 'w', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            pass

    def _log(self, event, mins, label):
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write('%s %s %d %s\n' % (
                    event, datetime.now().isoformat(), mins, label))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def toggle_dark_mode(self):
        if self.dark_mode.get():
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    def apply_dark_theme(self):
        from pomodoro_common import apply_dark_theme
        apply_dark_theme()

    def apply_light_theme(self):
        from pomodoro_common import apply_light_theme
        apply_light_theme()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def on_close(self):
        for tid in list(self.timers.keys()):
            self._kill_timer(tid)
        self.master.destroy()
