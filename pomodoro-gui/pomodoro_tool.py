"""
pomodoro_tool.py - Pomodoro + to-do + task scheduler (Windows).
Usage:
  python pomodoro_tool.py todo add "Buy milk"
  python pomodoro_tool.py todo list
  python pomodoro_tool.py todo done <id>
  python pomodoro_tool.py todo rm <id>
  python pomodoro_tool.py pomo <minutes> [task_id]
  python pomodoro_tool.py schedule add "Every day 09:00" 25 "Morning focus"
  python pomodoro_tool.py schedule list
  python pomodoro_tool.py schedule rm <id>
  python pomodoro_tool.py schedule run-now
Data stored in ~/pomodoro_data.json
"""
import sys, os, json, time, threading, subprocess, winsound, ctypes, uuid
from datetime import datetime, timedelta

DATA_FILE = os.path.expanduser('~/pomodoro_data.json')
STATUS = os.path.expanduser('~/pomodoro_status.txt')

# Eisenhower / Isover matrix — priority codes
# Q1: urgent + important  (do now)
# Q2: not urgent + important (schedule)
# Q3: urgent + not important (delegate)
# Q4: not urgent + not important (eliminate)
PRIORITY_Q1 = 1   # urgent & important
PRIORITY_Q2 = 2   # important, not urgent
PRIORITY_Q3 = 3   # urgent, not important
PRIORITY_Q4 = 4   # neither
PQ_LABEL = {
    PRIORITY_Q1: 'Q1-do',
    PRIORITY_Q2: 'Q2-schedule',
    PRIORITY_Q3: 'Q3-delegate',
    PRIORITY_Q4: 'Q4-eliminate',
}

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'todos': [], 'schedules': []}

def save(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def status_msg(msg):
    with open(STATUS, 'w', encoding='utf-8') as f:
        f.write(msg + '\n')

def _fire_sound():
    """Tiered sound: Beep (direct hardware) + SystemExclamation + SystemAsterisk.
    Try all three; if any one works the user hears something."""
    try:
        # 1) Hardware Beep — most reliable, 800Hz double
        winsound.Beep(800, 250)
        time.sleep(0.12)
        winsound.Beep(800, 250)
    except Exception:
        pass
    try:
        # 2) SystemExclamation
        winsound.PlaySound('SystemExclamation', winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass
    try:
        # 3) SystemAsterisk — third channel, different timbre
        winsound.PlaySound('SystemAsterisk', winsound.SND_ALIAS | winsound.SND_SYNC)
    except Exception:
        pass


def notify(title='Pomodoro', message='Done', sound=True):
    if sound:
        _fire_sound()
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
    script = os.path.expanduser('~/pomodoro_notify_tmp.ps1')
    try:
        with open(script, 'w', encoding='utf-8') as f:
            xml = ('<toast duration="short"><visual><binding template="ToastGeneric">'
                   '<text>%s</text><text>%s</text></binding></visual></toast>'
                   % (title.replace('"', ''), message.replace('"', '')))
            f.write('$xml = @"' + xml + '@"' + '\n')
            f.write('$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)' + '\n')
            f.write('[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("HermesPomodoro").Show($toast)' + '\n')
        subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# TIMER
# ---------------------------------------------------------------------------
def run_pomo(minutes, label='Focus'):
    sec = int(minutes * 60)
    status_msg('pomodoro: %dm (%s) | running' % (minutes, label))
    t0 = time.time()
    while True:
        elapsed = int(time.time() - t0)
        if elapsed >= sec:
            break
        rem = sec - elapsed
        status_msg('pomodoro: %dm (%s) | elapsed %ds / %ds | %ds left' % (minutes, label, elapsed, sec, rem))
        time.sleep(1)
    status_msg('pomodoro: %dm (%s) | DONE' % (minutes, label))
    notify('Pomodoro Done', '%s — %d minutes elapsed.' % (label, minutes))
    print('POMODORO DONE: %s (%d min)' % (label, minutes))

# ---------------------------------------------------------------------------
# TODO
# ---------------------------------------------------------------------------
def todo_add(desc, priority=None):
    data = load()
    todo = {'id': str(uuid.uuid4())[:8], 'desc': desc, 'created': datetime.now().isoformat(),
            'done': False, 'priority': priority, 'pomodoros': 0}
    data['todos'].append(todo)
    save(data)
    pq = PQ_LABEL.get(priority, '') if priority else ''
    print('TODO added: [%s] %s %s (pomodoros: 0)' % (todo['id'], desc,
          ('[' + pq + ']') if pq else ''))

def todo_list():
    data = load()
    todos = data['todos']
    if not todos:
        print('No todos.')
        return
    # sort: priority ascending (Q1 first), then created descending (newest first)
    from datetime import datetime as _dt
    def sort_key(t):
        p = t.get('priority')
        pnum = p if p in (PRIORITY_Q1, PRIORITY_Q2, PRIORITY_Q3, PRIORITY_Q4) else 99
        try:
            ts = _dt.fromisoformat(t['created']).timestamp()
        except (ValueError, KeyError):
            ts = 0.0
        return (pnum, -ts)
    todos = sorted(todos, key=sort_key)
    for t in todos:
        mark = 'x' if t['done'] else ' '
        pq = t.get('priority')
        label = PQ_LABEL.get(pq, '') if pq else ''
        pomo = t.get('pomodoros', 0)
        print('[%s] %s %s  %s %s  (pomodoros: %d)' % (
            t['id'], mark, t['desc'], t['created'][:10],
            ('[' + label + ']') if label else '', pomo))

def todo_done(tid):
    data = load()
    found = False
    for t in data['todos']:
        if t['id'] == tid:
            t['done'] = True
            found = True
            break
    if not found:
        print('No todo with id %s' % tid)
        return
    save(data)
    print('TODO marked done: [%s]' % tid)

def todo_rm(tid):
    data = load()
    before = len(data['todos'])
    data['todos'] = [t for t in data['todos'] if t['id'] != tid]
    if len(data['todos']) == before:
        print('No todo with id %s' % tid)
        return
    save(data)
    print('TODO removed: [%s]' % tid)

# ---------------------------------------------------------------------------
# SCHEDULE (Windows Task Scheduler via schtasks)
# ---------------------------------------------------------------------------
SCHED_PREFIX = 'HermesPomodoro_'

def _task_name(uid):
    return SCHED_PREFIX + uid

def schedule_add(cron_or_every, minutes, label):
    """cron_or_every examples:
       'Every day 09:00'
       'Every Monday 10:30'
       'Every 2 hours'
    We translate common phrases to schtasks /sc and /mo flags."""
    data = load()
    uid = str(uuid.uuid4())[:8]
    name = _task_name(uid)
    task_cmd = 'pythonw.exe "%s" run-only %d "%s"' % (
        os.path.expanduser('~/pomodoro_tool.py').replace('\\', '/'),
        minutes, label.replace('"', '')
    )
    # Parse schedule type
    txt = cron_or_every.strip()
    sc = None
    mo = None
    start = None
    # daily
    if txt.lower().startswith('every day'):
        sc = 'DAILY'
        # extract time
        rest = txt[9:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every monday'):
        sc = 'WEEKLY'; mo = 'MON'
        rest = txt[12:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every tuesday'):
        sc = 'WEEKLY'; mo = 'TUE'
        rest = txt[13:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every wednesday'):
        sc = 'WEEKLY'; mo = 'WED'
        rest = txt[14:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every thursday'):
        sc = 'WEEKLY'; mo = 'THU'
        rest = txt[15:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every friday'):
        sc = 'WEEKLY'; mo = 'FRI'
        rest = txt[14:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every saturday'):
        sc = 'WEEKLY'; mo = 'SAT'
        rest = txt[15:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every sunday'):
        sc = 'WEEKLY'; mo = 'SUN'
        rest = txt[14:].strip()
        if ':' in rest:
            start = rest
    elif txt.lower().startswith('every ') and 'hour' in txt.lower():
        sc = 'HOURLY'
        parts = txt.split()
        for p in parts:
            if p.isdigit():
                mo = int(p)
                break
    elif txt.lower().startswith('every ') and 'min' in txt.lower():
        sc = 'MINUTE'
        parts = txt.split()
        for p in parts:
            if p.isdigit():
                mo = int(p)
                break
    else:
        # try time-only
        if ':' in txt:
            start = txt
            sc = 'DAILY'
        else:
            print('Cannot parse schedule: %s' % txt)
            print('Examples: "Every day 09:00", "Every Monday 10:30", "Every 2 hours"')
            return

    args = ['schtasks', '/Create', '/SC', sc, '/TN', name, '/TR', task_cmd]
    if mo:
        args += ['/MO', str(mo)]
    if start:
        args += ['/ST', start]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print('schtasks failed:')
            print(r.stdout)
            print(r.stderr)
            return
    except Exception as e:
        print('schtasks error:', e)
        return

    entry = {
        'id': uid,
        'spec': txt,
        'minutes': minutes,
        'label': label,
        'taskname': name,
        'created': datetime.now().isoformat()
    }
    data['schedules'].append(entry)
    save(data)
    print('Scheduled: [%s] %s — %d min (%s)' % (uid, label, minutes, txt))

def schedule_list():
    data = load()
    scheds = data['schedules']
    if not scheds:
        print('No scheduled pomodoros.')
        return
    print('Scheduled pomodoros (Windows Task Scheduler):')
    for s in scheds:
        print(' [%s] %s — %d min | %s' % (s['id'], s['label'], s['minutes'], s['spec']))
    print('')
    print('Also verify in Task Scheduler (taskschd.msc) under task names starting with', SCHED_PREFIX)

def schedule_rm(uid):
    data = load()
    found = None
    for s in data['schedules']:
        if s['id'] == uid:
            found = s
            break
    if not found:
        print('No schedule with id %s' % uid)
        return
    name = found['taskname']
    try:
        subprocess.run(['schtasks', '/Delete', '/TN', name, '/F'],
                       capture_output=True, text=True, timeout=30)
    except Exception as e:
        print('schtasks delete error:', e)
    data['schedules'] = [s for s in data['schedules'] if s['id'] != uid]
    save(data)
    print('Schedule removed: [%s] %s' % (uid, found['label']))

def schedule_run_now():
    """Trigger all scheduled tasks immediately via schtasks /Run."""
    data = load()
    names = [s['taskname'] for s in data['schedules']]
    if not names:
        print('No scheduled pomodoros to run now.')
        return
    for name in names:
        try:
            subprocess.run(['schtasks', '/Run', '/TN', name],
                           capture_output=True, text=True, timeout=15)
            print('Triggered:', name)
        except Exception as e:
            print('Failed to trigger', name, e)

# ---------------------------------------------------------------------------
# RUN-ONLY (called by scheduled tasks — silent, no console/terminal)
# ---------------------------------------------------------------------------
def run_only(minutes, label):
    sec = int(minutes * 60)
    log = os.path.expanduser('~/pomodoro_log.txt')
    with open(log, 'a', encoding='utf-8') as lf:
        lf.write('START %s %s %s\n' % (datetime.now().isoformat(), minutes, label))
    t0 = time.time()
    while True:
        elapsed = int(time.time() - t0)
        if elapsed >= sec:
            break
        time.sleep(max(0.5, sec - (time.time() - t0) - 0.25))
    with open(log, 'a', encoding='utf-8') as lf:
        lf.write('DONE %s %s %s\n' % (datetime.now().isoformat(), minutes, label))
    notify('Pomodoro Done', '%s — %d minutes elapsed.' % (label, minutes), sound=True)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0].lower()
    if cmd == 'todo':
        sub = args[1].lower() if len(args) > 1 else ''
        if sub == 'add':
            # optional priority: -q N (1-4) at end or -q N before desc
            # Collect desc and optional priority
            rest = args[2:]
            priority = None
            # If last arg is a bare number 1-4 and preceded by -q, pop it
            if len(rest) >= 2 and rest[-2].lower() in ('-q', '--priority') and rest[-1] in ('1','2','3','4'):
                priority = int(rest[-1])
                rest = rest[:-2]
            # Also accept bare number as priority if everything else looks like desc
            desc = ' '.join(rest)
            todo_add(desc, priority=priority)
        elif sub == 'list':
            todo_list()
        elif sub == 'done':
            todo_done(args[2])
        elif sub == 'rm':
            todo_rm(args[2])
        else:
            print('todo subcommands: add, list, done <id>, rm <id>')
    elif cmd == 'pomo':
        mins = int(args[1]) if len(args) > 1 else 1
        label = args[2] if len(args) > 2 else 'Focus'
        run_pomo(mins, label)
    elif cmd == 'schedule':
        sub = args[1].lower() if len(args) > 1 else ''
        if sub == 'add':
            if len(args) < 4:
                print('Usage: schedule add "<cron phrase>" <minutes> "<label>"')
                print('Examples:')
                print('  schedule add "Every day 09:00" 25 "Morning focus"')
                print('  schedule add "Every Monday 10:30" 15 "Weekly review"')
                print('  schedule add "Every 2 hours" 5 "Stretch break"')
                return
            spec = args[2]
            mins = int(args[3])
            label = ' '.join(args[4:]) if len(args) > 4 else spec
            schedule_add(spec, mins, label)
        elif sub == 'list':
            schedule_list()
        elif sub == 'rm':
            schedule_rm(args[2])
        elif sub == 'run-now':
            schedule_run_now()
        else:
            print('schedule subcommands: add, list, rm <id>, run-now')
    elif cmd == 'run-only':
        # Called by Task Scheduler
        mins = int(args[1]) if len(args) > 1 else 1
        label = args[2] if len(args) > 2 else 'Focus'
        run_only(mins, label)
    else:
        print('Commands: todo, pomo, schedule, run-only')
        print(__doc__)

if __name__ == '__main__':
    main()
