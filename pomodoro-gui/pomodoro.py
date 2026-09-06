"""
pomodoro.py - Win10 timer with sound + toast + console + status file.
Usage: python pomodoro.py [minutes]  (default 1)
"""
import sys, time, os, threading, subprocess, winsound

MIN = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SEC = MIN * 60
STATUS = os.path.expanduser('~/pomodoro_status.txt')

def status(msg):
    with open(STATUS, 'w', encoding='utf-8') as f:
        f.write(msg + '\n')

def countdown():
    t0 = time.time()
    status('pomodoro: %dm | elapsed 0s / %ds | running' % (MIN, SEC))
    while True:
        elapsed = int(time.time() - t0)
        if elapsed >= SEC:
            break
        rem = SEC - elapsed
        status('pomodoro: %dm | elapsed %ds / %ds | %ds remaining' % (MIN, elapsed, SEC, rem))
        time.sleep(1)
    status('pomodoro: %dm | DONE' % MIN)

def notify():
    # 1) sound
    try:
        winsound.PlaySound('SystemExclamation', winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception as e:
        print('sound channel failed:', e)

    # 2) console banner via WriteConsole (bypass msys newline translation)
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        h = kernel.GetStdHandle(-11)
        msg = b'\r\n\r\n########  POMODORO DONE  ########\r\n'
        kernel.WriteConsoleA(h, msg, len(msg), None, None)
        msg2 = b'1 minute elapsed.\r\n'
        kernel.WriteConsoleA(h, msg2, len(msg2), None, None)
    except Exception as e:
        print('console channel failed:', e)

    # 3) Windows toast via powershell + Windows.UI.Notifications
    script = os.path.expanduser('~/pomodoro_notify.ps1')
    try:
        with open(script, 'w', encoding='utf-8') as f:
            f.write('$xml = @"')
            f.write('<toast duration="short">')
            f.write('<visual><binding template="ToastGeneric">')
            f.write('<text>Pomodoro Done</text>')
            f.write('<text>1 minute elapsed.</text>')
            f.write('</binding></visual>')
            f.write('</toast>')
            f.write('@"')
            f.write('\n')
            f.write('$doc = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastGeneric)')
            f.write('\n')
            f.write('$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)')
            f.write('\n')
            f.write('[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("HermesPomodoro").Show($toast)')
            f.write('\n')
        subprocess.Popen(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print('toast channel failed:', e)

def main():
    status('pomodoro: %dm | starting' % MIN)
    threading.Thread(target=countdown, daemon=True).start()
    while True:
        with open(STATUS, encoding='utf-8') as f:
            line = f.readline()
        if 'DONE' in line:
            break
        time.sleep(0.5)
    notify()
    print('POMODORO DONE')

if __name__ == '__main__':
    main()
