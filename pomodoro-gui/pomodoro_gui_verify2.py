"""Headless verification: two tasks, start both timers, verify two cards + independent."""
import os, sys, time, threading
os.environ.setdefault('HOME', os.path.expanduser('~'))
os.chdir(os.path.expanduser('~'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pomodoro_gui import App, _load, _save

def main():
    r = __import__('tkinter').Tk()
    r.withdraw()
    app = App(r)
    r.update_idletasks()

    # kill leftovers
    for tid in list(app.timers.keys()):
        app._kill_timer(tid)
    r.update_idletasks(); time.sleep(0.3)

    data = _load()
    # find or add two tasks
    tasks = [t for t in data['todos'] if not t.get('done')]
    if len(tasks) < 2:
        for desc in ['card-A', 'card-B']:
            app.todo_desc.delete(0, 'end'); app.todo_desc.insert(0, desc)
            app.todo_q.set(2)
            app._todo_add()
            r.update_idletasks(); time.sleep(0.2)
        data = _load()
        tasks = [t for t in data['todos'] if not t.get('done')][-2:]
    ta, tb = tasks[0], tasks[1]
    tid_a, tid_b = ta['id'], tb['id']

    # select A, start
    app.todo_tree.selection_set(tid_a)
    app._on_todo_select(); r.update_idletasks(); time.sleep(0.3)
    app._panel_start()
    r.update_idletasks(); time.sleep(0.5)

    cards_a = list(app._task_cards.keys())
    print('after start A — cards:', cards_a, '| A running:', app.timers.get(tid_a)['runner'].paused == False and not app.timers[tid_a]['runner'].done)

    # select B, start
    app.todo_tree.selection_set(tid_b)
    app._on_todo_select(); r.update_idletasks(); time.sleep(0.3)
    app._panel_start()
    r.update_idletasks(); time.sleep(0.5)

    cards_b = list(app._task_cards.keys())
    print('after start B — cards:', cards_b)
    print('both running:', len(cards_b) == 2)
    print('A card exists:', tid_a in app._task_cards)
    print('B card exists:', tid_b in app._task_cards)

    # wait for both to finish (1 min each — poll 90s)
    deadline = time.time() + 95
    done_a = done_b = False
    while time.time() < deadline:
        r.update_idletasks(); r.update()
        ra = app.timers.get(tid_a)
        rb = app.timers.get(tid_b)
        if ra and ra['runner'].done: done_a = True
        if rb and rb['runner'].done: done_b = True
        if done_a and done_b:
            break
        time.sleep(0.5)

    print('A done:', done_a, '| B done:', done_b)
    print('A pomo after:', _load()['todos'][-2].get('pomodoros') if len(_load()['todos']) >= 2 else '?')
    print('B pomo after:', _load()['todos'][-1].get('pomodoros') if len(_load()['todos']) >= 1 else '?')
    print('cards remaining:', list(app._task_cards.keys()))
    print('RESULT:', 'PASS' if done_a and done_b and tid_a not in app._task_cards and tid_b not in app._task_cards else 'FAIL')
    r.destroy()
    return 0 if (done_a and done_b) else 1

if __name__ == '__main__':
    sys.exit(main())
