"""
pomofocus_replica.py — exact replica of pomofocus.io features, CLI + file-based storage.
Features:
  - Customizable timer: focus, short break, long break, rounds before long break, alarm sound, background sound
  - Task list with per-task pomodoro estimates
  - Select task to start timer (auto-chaining: short break after focus, long break after N rounds)
  - Templates (save/load repetitive daily tasks)
  - Reports: daily, weekly, monthly focus time
  - Sound + toast notifications
  - Activity log (matches pomotroid-style timer activity logging)

Usage:
  python pomofocus_replica.py settings          # show current settings
  python pomofocus_replica.py settings set focus=25 short=5 long=15 rounds=4 sound=SystemExclamation bgsound=None
  python pomofocus_replica.py tasks add "Read Chapter 3" 4
  python pomofocus_replica.py tasks list
  python pomofocus_replica.py tasks start "Read Chapter 3"   # starts timer for that task
  python pomofocus_replica.py tasks complete <id>             # mark task done (with pomodoro count)
  python pomofocus_replica.py tasks estimate <id> <count>    # set estimate
  python pomofocus_replica.py templates save "Daily Study"    # save current task list as template
  python pomofocus_replica.py templates load "Daily Study"    # load template into tasks
  python pomofocus_replica.py templates list
  python pomofocus_replica.py templates rm "Daily Study"
  python pomofocus_replica.py report today
  python pomofocus_replica.py report week
  python pomofocus_replica.py report month
  python pomofocus_replica.py report task "Read Chapter 3"
  python pomofocus_replica.py timer 25                        # standalone timer (no task)
  python pomofocus_replica.py timer --task "Read Chapter 3"   # timer with task
  python pomofocus_replica.py timer --auto                     # starts first uncompleted task with auto-breaks
Data: ~/pomofocus_data.json
"""

import sys, os, json, time, uuid, subprocess, winsound, ctypes, re
from datetime import datetime, timedelta
from collections import defaultdict

DATA = os.path.expanduser('~/pomofocus_data.json')
LOG = os.path.expanduser('~/pomofocus_log.txt')
STATUS = os.path.expanduser('~/pomofocus_status.txt')

DEFAULT_SETTINGS = {
    'focus': 25,
    'short': 5,
    'long': 15,
    'rounds': 4,           # number of pomodoros before a long break
    'sound': 'SystemExclamation',
    'bgsound': None,        # background sound file or None
    'auto_start_next': True,
}

def load_data():
    if os.path.exists(DATA):
        with open(DATA, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'settings': dict(DEFAULT_SETTINGS), 'tasks': [], 'templates': {}, 'completed': []}

def save_data(d):
    with open(DATA, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

def log_event(kind, **kw):
    entry = {'time': datetime.now().isoformat(), 'kind': kind}
    entry.update(kw)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def status_msg(msg):
    with open(STATUS, 'w', encoding='utf-8') as f:
        f.write(msg + '\n')

def notify(title='Pomofocus', message='Done', sound=True):
    if sound:
        try:
            winsound.PlaySound(DEFAULT_SETTINGS.get('sound', 'SystemExclamation'),
                               winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass
    # console
    try:
        kernel = ctypes.windll.kernel32
        h = kernel.GetStdHandle(-11)
        banner = b'\r\n\r\n########  ' + title.encode() + b'  ########\r\n'
        kernel.WriteConsoleA(h, banner, len(banner), None, None)
        body = message.encode() + b'\r\n'
        kernel.WriteConsoleA(h, body, len(body), None, None)
    except Exception:
        pass
    # toast
    script = os.path.expanduser('~/pomofocus_notify_tmp.ps1')
    try:
        safe_title = title.replace('"', '').replace('&', 'and')
        safe_msg = message.replace('"', '').replace('&', 'and')
        xml = ('<toast duration="short"><visual><binding template="ToastGeneric">'
               '<text>%s</text><text>%s</text></binding></visual></toast>'
               % (safe_title, safe_msg))
        with open(script, 'w', encoding='utf-8') as f:
            f.write('$xml = @"' + xml + '@"' + '\n')
            f.write('$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)' + '\n')
            f.write('[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Pomofocus").Show($toast)' + '\n')
        subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def parse_terminal_bool(val):
    return val.strip().lower() in ('true', '1', 'yes', 'on')

def round_to_nearest(v, base):
    return base * round(v / base)

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
def cmd_settings():
    d = load_data()
    s = d['settings']
    print('Current settings:')
    print('  Focus time:       %d min' % s['focus'])
    print('  Short break:      %d min' % s['short'])
    print('  Long break:       %d min' % s['long'])
    print('  Rounds before long break: %d' % s['rounds'])
    print('  Alarm sound:      %s' % s['sound'])
    print('  Background sound: %s' % (s['bgsound'] or 'None'))
    print('  Auto-start next task: %s' % s['auto_start_next'])

def cmd_settings_set(args):
    d = load_data()
    s = d['settings']
    i = 0
    while i < len(args):
        a = args[i]
        if '=' in a:
            k, v = a.split('=', 1)
            k = k.strip()
            v = v.strip()
            if k == 'focus':
                s['focus'] = max(1, int(v))
            elif k == 'short':
                s['short'] = max(1, int(v))
            elif k == 'long':
                s['long'] = max(1, int(v))
            elif k == 'rounds':
                s['rounds'] = max(1, int(v))
            elif k == 'sound':
                s['sound'] = v
            elif k == 'bgsound':
                s['bgsound'] = v if v.lower() != 'none' else None
            elif k == 'auto_start_next':
                s['auto_start_next'] = parse_terminal_bool(v)
            else:
                print('Unknown setting:', k)
            i += 1
        else:
            print('Use key=value pairs, e.g.: focus=25 short=5')
            return
    save_data(d)
    print('Settings updated.')
    cmd_settings()

# ---------------------------------------------------------------------------
# TASKS
# ---------------------------------------------------------------------------
def now_iso():
    return datetime.now().isoformat()

def cmd_tasks_add(desc, estimate):
    d = load_data()
    tid = str(uuid.uuid4())[:8]
    est = max(1, int(estimate))
    task = {
        'id': tid,
        'desc': desc,
        'estimate': est,
        'completed_pomodoros': 0,
        'created': now_iso(),
        'done': False,
        'done_at': None,
    }
    d['tasks'].append(task)
    save_data(d)
    print('Task added: [%s] %s — estimate %d pomodoros' % (tid, desc, est))

def cmd_tasks_list():
    d = load_data()
    tasks = d['tasks']
    if not tasks:
        print('No tasks.')
        return
    print('Tasks:')
    for t in tasks:
        mark = '✓' if t.get('done') else '○'
        status = 'DONE' if t.get('done') else 'active'
        print(' [%s] %s %-45s estimate=%d pomodoros done=%d %s' % (
            t['id'], mark, t['desc'][:45], t['estimate'], t['completed_pomodoros'], status))

def cmd_tasks_estimate(tid, count):
    d = load_data()
    for t in d['tasks']:
        if t['id'] == tid:
            t['estimate'] = max(1, int(count))
            save_data(d)
            print('Task [%s] estimate set to %d pomodoros' % (tid, count))
            return
    print('Task not found:', tid)

def cmd_tasks_complete(tid):
    d = load_data()
    for t in d['tasks']:
        if t['id'] == tid:
            t['done'] = True
            t['done_at'] = now_iso()
            save_data(d)
            print('Task [%s] marked done: %s' % (tid, t['desc']))
            return
    print('Task not found:', tid)

def cmd_tasks_delete(tid):
    d = load_data()
    before = len(d['tasks'])
    d['tasks'] = [t for t in d['tasks'] if t['id'] != tid]
    if len(d['tasks']) == before:
        print('Task not found:', tid)
        return
    save_data(d)
    print('Task deleted:', tid)

def find_task(desc_or_id):
    """Find a task by id or by fuzzy desc match."""
    d = load_data()
    # try exact id first
    for t in d['tasks']:
        if t['id'] == desc_or_id:
            return t
    # try startswith desc
    for t in d['tasks']:
        if t['desc'].lower().startswith(desc_or_id.lower()):
            return t
    # try contains
    for t in d['tasks']:
        if desc_or_id.lower() in t['desc'].lower():
            return t
    return None

def cmd_tasks_start(desc_or_id):
    """Start a timer for a specific task. This is the task→timer linking feature.
    After the focus timer ends, mark one pomodoro done for the task, then auto short break,
    then auto long break if rounds reached."""
    task = find_task(desc_or_id)
    if not task:
        print('Task not found. Use tasks list to see ids.')
        return
    if task.get('done'):
        print('Task already done. Use tasks estimate to continue or tasks delete to remove.')
        return
    _run_timer_with_task(task, 'manual_start')

def cmd_tasks_auto_start():
    """Start the first uncompleted, non-done task automatically. Matches pomofocus 'select task and start' flow."""
    d = load_data()
    candidates = [t for t in d['tasks'] if not t.get('done')]
    if not candidates:
        print('No active tasks. Add one with tasks add.')
        return
    task = candidates[0]
    print('Auto-starting task: [%s] %s (estimate %d)' % (task['id'], task['desc'], task['estimate']))
    _run_timer_with_task(task, 'auto_start')

# ---------------------------------------------------------------------------
# TIMER (core) — supports standalone, task-bound, and auto-break chaining
# ---------------------------------------------------------------------------
def _run_timer_with_task(task, start_mode):
    """Run a pomodoro session for a task, with break chaining."""
    d = load_data()
    s = d['settings']
    focus = s['focus']
    short = s['short']
    long_ = s['long']
    rounds = s['rounds']
    sound = s['sound']

    # Track rounds for this task session
    task_rounds_done = task.get('completed_pomodoros', 0)
    pane_index = task.get('_pane_index', 0)  # which pomodoro in current session
    pane_index += 1

    # Focus timer
    _focus_timer(focus, task, start_mode, pane_index)

    # Mark pomodoro done
    task['completed_pomodoros'] = task.get('completed_pomodoros', 0) + 1
    task['_pane_index'] = pane_index
    task_rounds_done += 1
    save_data(d)
    log_event('pomodoro_done', task_id=task['id'], task_desc=task['desc'],
              focus_min=focus, round=task_rounds_done)

    # Check if task is complete (estimate reached)
    if task['completed_pomodoros'] >= task['estimate']:
        task['done'] = True
        task['done_at'] = now_iso()
        save_data(d)
        log_event('task_completed', task_id=task['id'], task_desc=task['desc'])
        notify('Task Complete', '%s — %d pomodoros done.' % (task['desc'], task['completed_pomodoros']))
        print('TASK COMPLETE: %s (%d pomodoros)' % (task['desc'], task['completed_pomodoros']))
        # No break needed — task is done
        return

    # Break chaining
    if task_rounds_done % rounds == 0:
        # Long break
        print('--- LONG BREAK %d min ---' % long_)
        status_msg('pomodoro: LONG BREAK %d min | task %s' % (long_, task['desc']))
        _break_timer(long_, 'long break')
        notify('Long Break Done', 'Take a break. Ready to start next pomodoro?')
    else:
        # Short break
        print('--- SHORT BREAK %d min ---' % short)
        status_msg('pomodoro: SHORT BREAK %d min | task %s' % (short, task['desc']))
        _break_timer(short, 'short break')
        notify('Short Break Done', 'Break over. Ready for next pomodoro?')

    # Auto-start next pomodoro if enabled
    if s.get('auto_start_next', True) and not task.get('done'):
        print('--- AUTO-STARTING NEXT POMODORO ---')
        _run_timer_with_task(task, 'auto_next')
    else:
        print('Session paused. Run "tasks start %s" or "timer --auto" to continue.' % task['id'])

def _focus_timer(minutes, task, start_mode, pane_index):
    """Core focus timer with status updates."""
    sec = int(minutes * 60)
    label = task['desc'] if task else 'Focus'
    status_msg('pomodoro: FOCUS %dm | %s | round %d | running' % (minutes, label, pane_index))
    t0 = time.time()
    while True:
        elapsed = int(time.time() - t0)
        if elapsed >= sec:
            break
        rem = sec - elapsed
        status_msg('pomodoro: FOCUS %dm | %s | round %d | %d:%02d remaining' % (
            minutes, label, pane_index, rem // 60, rem % 60))
        time.sleep(1)
    status_msg('pomodoro: FOCUS %dm | %s | round %d | DONE' % (minutes, label, pane_index))
    notify('Pomodoro Complete', '%s — %d min focus done (round %d).' % (label, minutes, pane_index))
    print('FOCUS %d min done (round %d).' % (minutes, pane_index))
    log_event('focus_timer_done', task_id=task['id'] if task else None,
              task_desc=task['desc'] if task else None,
              focus_min=minutes, round=pane_index, start_mode=start_mode)

def _break_timer(minutes, kind):
    """Break timer (short or long) — simple count with status."""
    sec = int(minutes * 60)
    t0 = time.time()
    while True:
        elapsed = int(time.time() - t0)
        if elapsed >= sec:
            break
        rem = sec - elapsed
        status_msg('pomodoro: %s %dm | %d:%02d remaining' % (kind, minutes, rem // 60, rem % 60))
        time.sleep(1)
    status_msg('pomodoro: %s %dm | DONE' % (kind, minutes))
    print('%s %d min done.' % (kind, minutes))
    log_event('break_done', break_type=kind, minutes=minutes)

def cmd_timer(args):
    """Standalone timer mode — no task linkage."""
    task = None
    auto = False
    minutes = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--task' and i+1 < len(args):
            t = find_task(args[i+1])
            if t:
                task = t
                i += 1
            else:
                print('Task not found:', args[i+1])
                return
        elif a == '--auto':
            auto = True
        else:
            try:
                minutes = int(a)
            except ValueError:
                print('Unknown timer arg:', a)
                return
        i += 1

    if auto:
        cmd_tasks_auto_start()
        return

    if minutes is None:
        d = load_data()
        minutes = d['settings']['focus']
        print('No minutes specified, using focus setting: %d min' % minutes)

    if task:
        _run_timer_with_task(task, 'standalone_with_task')
    else:
        _run_timer_with_task(None, 'standalone')
        # For standalone (no task), still mark a virtual pomodoro in log but no task tracking
        log_event('standalone_pomodoro', focus_min=minutes)

# ---------------------------------------------------------------------------
# TEMPLATES
# ---------------------------------------------------------------------------
def cmd_templates_save(name):
    d = load_data()
    tasks = [t for t in d['tasks'] if not t.get('done')]
    if not tasks:
        print('No active tasks to save as template.')
        return
    d['templates'][name] = {
        'saved_at': now_iso(),
        'tasks': [{'desc': t['desc'], 'estimate': t['estimate']} for t in tasks],
    }
    save_data(d)
    print('Template saved: "%s" with %d tasks' % (name, len(tasks)))

def cmd_templates_load(name):
    d = load_data()
    tmpl = d['templates'].get(name)
    if not tmpl:
        print('Template not found:', name)
        print('Available templates:', list(d['templates'].keys()))
        return
    for t in tmpl['tasks']:
        tid = str(uuid.uuid4())[:8]
        d['tasks'].append({
            'id': tid,
            'desc': t['desc'],
            'estimate': t['estimate'],
            'completed_pomodoros': 0,
            'created': now_iso(),
            'done': False,
            'done_at': None,
        })
    save_data(d)
    print('Template "%s" loaded: %d tasks added.' % (name, len(tmpl['tasks'])))

def cmd_templates_list():
    d = load_data()
    tpls = d['templates']
    if not tpls:
        print('No templates saved.')
        return
    print('Templates:')
    for name, t in tpls.items():
        print(' "%s" — saved %s, %d tasks' % (name, t['saved_at'][:10], len(t['tasks'])))

def cmd_templates_rm(name):
    d = load_data()
    if name not in d['templates']:
        print('Template not found:', name)
        return
    del d['templates'][name]
    save_data(d)
    print('Template deleted:', name)

# ---------------------------------------------------------------------------
# REPORTS — daily, weekly, monthly, per-task
# ---------------------------------------------------------------------------
def parse_log_entries(kind=None, days=None, task_id=None):
    """Read log and filter entries."""
    if not os.path.exists(LOG):
        return []
    entries = []
    with open(LOG, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if kind and e.get('kind') not in kind:
                continue
            if task_id and e.get('task_id') != task_id:
                continue
            entries.append(e)
    if days is not None:
        cutoff = datetime.now() - timedelta(days=days)
        entries = [e for e in entries if e.get('time', '') > cutoff.isoformat()]
    return entries

def cmd_report(kind):
    d = load_data()
    if kind == 'today':
        _report_today(d)
    elif kind == 'week':
        _report_week(d)
    elif kind == 'month':
        _report_month(d)
    elif kind == 'task':
        if len(sys.argv) < 4:
            print('Usage: report task "<task desc or id>"')
            return
        tid_or_desc = sys.argv[3]
        _report_task(tid_or_desc, d)
    else:
        print('Unknown report:', kind)
        print('Reports: today, week, month, task "<desc>"')

def _read_log():
    if not os.path.exists(LOG):
        return []
    out = []
    with open(LOG, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out

def _focus_minutes_today(d):
    entries = _read_log()
    today = datetime.now().date().isoformat()
    total = 0
    for e in entries:
        if e.get('kind') == 'focus_timer_done':
            ts = e.get('time', '')
            if ts.startswith(today):
                total += e.get('focus_min', 0)
    return total

def _focus_minutes_week(d):
    entries = _read_log()
    now = datetime.now()
    week_ago = now - timedelta(days=now.weekday())  # Monday
    total = 0
    for e in entries:
        if e.get('kind') == 'focus_timer_done':
            ts = e.get('time', '')
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            if dt >= week_ago:
                total += e.get('focus_min', 0)
    return total

def _focus_minutes_month(d):
    entries = _read_log()
    now = datetime.now()
    total = 0
    for e in entries:
        if e.get('kind') == 'focus_timer_done':
            ts = e.get('time', '')
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            if dt.year == now.year and dt.month == now.month:
                total += e.get('focus_min', 0)
    return total

def _report_today(d):
    mins = _focus_minutes_today(d)
    tasks_done = len([t for t in d['tasks'] if t.get('done')])
    active = len([t for t in d['tasks'] if not t.get('done')])
    print('=== TODAY ===')
    print('Focus time today: %d min (%d h %d min)' % (mins, mins // 60, mins % 60))
    print('Pomodoros (focus rounds): %d' % (mins // d['settings']['focus']))
    print('Tasks done today: %d' % tasks_done)
    print('Active tasks: %d' % active)

def _report_week(d):
    mins = _focus_minutes_week(d)
    print('=== THIS WEEK (Mon–Sun) ===')
    print('Focus time: %d min (%d h %d min)' % (mins, mins // 60, mins % 60))
    print('Pomodoros: %d' % (mins // d['settings']['focus']))

def _report_month(d):
    mins = _focus_minutes_month(d)
    print('=== THIS MONTH ===')
    print('Focus time: %d min (%d h %d min)' % (mins, mins // 60, mins % 60))
    print('Pomodoros: %d' % (mins // d['settings']['focus']))

def _report_task(tid_or_desc, d):
    task = find_task(tid_or_desc)
    if not task:
        print('Task not found.')
        return
    entries = _read_log()
    total = 0
    for e in entries:
        if e.get('kind') == 'focus_timer_done' and e.get('task_id') == task['id']:
            total += e.get('focus_min', 0)
    print('=== TASK: %s ===' % task['desc'])
    print('ID: %s' % task['id'])
    print('Estimate: %d pomodoros' % task['estimate'])
    print('Completed pomodoros: %d' % task['completed_pomodoros'])
    print('Total focus time logged: %d min (%d h %d min)' % (total, total // 60, total % 60))
    if task.get('done'):
        print('Status: DONE at %s' % (task.get('done_at', 'unknown')[:10]))
    else:
        remaining = max(0, task['estimate'] - task['completed_pomodoros'])
        print('Remaining: %d pomodoros' % remaining)

# ---------------------------------------------------------------------------
# STANDALONE TIMER CLI (no task)
# ---------------------------------------------------------------------------
def cmd_standalone_timer(minutes=None):
    d = load_data()
    s = d['settings']
    mins = minutes if minutes else s['focus']
    _focus_timer(mins, None, 'standalone', 0)
    log_event('standalone_pomodoro', focus_min=mins)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_help():
    print(__doc__)

def main():
    args = sys.argv[1:]
    if not args:
        print_help()
        return
    cmd = args[0].lower()
    if cmd == 'settings':
        if len(args) > 1 and args[1].lower() == 'set':
            cmd_settings_set(args[2:])
        else:
            cmd_settings()
    elif cmd == 'tasks':
        sub = args[1].lower() if len(args) > 1 else ''
        if sub == 'add':
            if len(args) < 4:
                print('Usage: tasks add "<desc>" <estimate>')
                return
            cmd_tasks_add(' '.join(args[2:-1]), args[-1])
        elif sub == 'list':
            cmd_tasks_list()
        elif sub == 'estimate':
            if len(args) < 4:
                print('Usage: tasks estimate <id> <count>')
                return
            cmd_tasks_estimate(args[2], args[3])
        elif sub == 'complete':
            if len(args) < 3:
                print('Usage: tasks complete <id>')
                return
            cmd_tasks_complete(args[2])
        elif sub == 'delete':
            if len(args) < 3:
                print('Usage: tasks delete <id>')
                return
            cmd_tasks_delete(args[2])
        elif sub == 'start':
            if len(args) < 3:
                print('Usage: tasks start <id or desc>')
                return
            cmd_tasks_start(args[2])
        else:
            print('Task subcommands: add, list, estimate, complete, delete, start')
    elif cmd == 'templates':
        sub = args[1].lower() if len(args) > 1 else ''
        if sub == 'save':
            if len(args) < 3:
                print('Usage: templates save "<name>"')
                return
            cmd_templates_save(' '.join(args[2:]))
        elif sub == 'load':
            if len(args) < 3:
                print('Usage: templates load "<name>"')
                return
            cmd_templates_load(' '.join(args[2:]))
        elif sub == 'list':
            cmd_templates_list()
        elif sub == 'rm':
            if len(args) < 3:
                print('Usage: templates rm "<name>"')
                return
            cmd_templates_rm(' '.join(args[2:]))
        else:
            print('Template subcommands: save, load, list, rm')
    elif cmd == 'report':
        if len(args) < 2:
            print('Usage: report <today|week|month|task "<desc>">')
            return
        cmd_report(args[1])
    elif cmd == 'timer':
        # timer <minutes> [--task <id>] [--auto]
        timer_args = args[1:]
        cmd_timer(timer_args)
    else:
        print('Unknown command:', cmd)
        print_help()

if __name__ == '__main__':
    main()
