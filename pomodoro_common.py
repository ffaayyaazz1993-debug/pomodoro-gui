"""
pomodoro_common.py — shared runtime for the pomodoro GUI + CLI tool.

Paths, Eisenhower constants, data helpers, sound + toast, TimerRunner,
ChamferNotebook, theme helpers, mindmap geometry — all reusable by any
consumer. GUI (pomodoro_gui.py) and CLI (pomodoro_tool.py) import from here.
"""

import os
import sys
import json
import time
import uuid
import queue
import threading
import subprocess
import winsound
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_FILE = os.path.expanduser('~/pomodoro_data.json')
STATUS_FILE = os.path.expanduser('~/pomodoro_status.txt')
LOG_FILE = os.path.expanduser('~/pomodoro_log.txt')
PROG = os.path.abspath(__file__) if '__file__' in globals() else os.path.abspath(sys.argv[0])

# ---------------------------------------------------------------------------
# Eisenhower / Isover matrix — priority codes
# ---------------------------------------------------------------------------
Q1, Q2, Q3, Q4 = 1, 2, 3, 4
PQ_LABEL = {Q1: 'Q1-do', Q2: 'Q2-schedule', Q3: 'Q3-delegate', Q4: 'Q4-eliminate'}

PRIORITY_Q1 = Q1   # urgent & important
PRIORITY_Q2 = Q2   # important, not urgent
PRIORITY_Q3 = Q3   # urgent, not important
PRIORITY_Q4 = Q4   # neither

# ---------------------------------------------------------------------------
# Data helpers — shared by GUI and CLI
# ---------------------------------------------------------------------------
def load():
    """Load pomodoro_data.json, migrating old flat format to projects if needed."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'projects' not in data:
                data = {
                    'projects': [
                        {
                            'id': 'default',
                            'name': 'Default Project',
                            'todos': data.get('todos', []),
                            'schedules': data.get('schedules', []),
                        }
                    ],
                    'current_project': 'default',
                    'mindmaps': data.get('mindmaps', []),
                    'current_mindmap': data.get('current_mindmap', None),
                }
            if 'mindmaps' not in data:
                data['mindmaps'] = []
            if 'current_mindmap' not in data:
                data['current_mindmap'] = None
            return data
    return {
        'projects': [{'id': 'default', 'name': 'Default Project', 'todos': [], 'schedules': []}],
        'current_project': 'default',
        'mindmaps': [],
        'current_mindmap': None,
    }


def save(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_current_project(data):
    pid = data.get('current_project', 'default')
    for p in data.get('projects', []):
        if p['id'] == pid:
            return p
    if data.get('projects'):
        return data['projects'][0]
    return None


def all_todos(data):
    """Yield every todo from every project."""
    for project in data.get('projects', []):
        for todo in project.get('todos', []):
            yield todo


# ---------------------------------------------------------------------------
# Sound + toast
# ---------------------------------------------------------------------------
def fire_sound():
    try:
        winsound.Beep(800, 250)
        time.sleep(0.12)
        winsound.Beep(800, 250)
    except Exception:
        pass
    try:
        winsound.PlaySound('SystemExclamation', winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass
    try:
        winsound.PlaySound('SystemAsterisk', winsound.SND_ALIAS | winsound.SND_SYNC)
    except Exception:
        pass


def toast(title, message):
    script = os.path.expanduser('~/pomodoro_notify_tmp.ps1')
    try:
        xml = ('<toast duration="short"><visual><binding template="ToastGeneric">'
               '<text>%s</text><text>%s</text></binding></visual></toast>'
               % (title.replace('"', ''), message.replace('"', '')))
        with open(script, 'w', encoding='utf-8') as f:
            f.write('$xml = @"' + xml + '"' + '\n')
            f.write('$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)' + '\n')
            f.write('[Windows.UI.Notifications.ToastNotificationManager]'
                    '::CreateToastNotifier("HermesPomodoro").Show($toast)' + '\n')
        subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy',
                          'Bypass', '-File', script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def notify(title='Pomodoro', message='Done', sound=True):
    if sound:
        fire_sound()
    try:
        kernel = ctypes.windll.kernel32
        h = kernel.GetStdHandle(-11)
        banner = b'\r\n\r\n########  ' + title.encode() + b'  ########\r\n'
        kernel.WriteConsoleA(h, banner, len(banner), None, None)
        body = message.encode() + b'\r\n'
        kernel.WriteConsoleA(h, body, len(body), None, None)
    except Exception:
        pass
    toast(title, message)


# ---------------------------------------------------------------------------
# Timer runner
# ---------------------------------------------------------------------------
class TimerRunner:
    def __init__(self, task_id, minutes, sound_on):
        self.task_id = task_id
        self.minutes = int(minutes)
        self.sound_on = sound_on
        self.sec_total = self.minutes * 60
        self.elapsed = 0
        self.done = False
        self.paused = False
        self.canceled = False
        self._start_time = None
        self._before_pause = 0.0

    def start(self):
        self._start_time = time.time()
        self._before_pause = 0.0
        self.paused = False
        self.done = False

    def pause(self):
        if self.done or self.canceled or self.paused:
            return
        self.paused = True
        self._before_pause = time.time() - self._start_time

    def resume(self):
        if self.done or self.canceled or not self.paused:
            return
        self._start_time = time.time() - self._before_pause
        self.paused = False

    def cancel(self):
        self.canceled = True
        self.done = True

    def tick(self):
        if self.done:
            return self.elapsed, self.sec_total, True, self.paused
        if self.paused:
            return self._before_pause, self.sec_total, False, True
        if self._start_time is None:
            return 0, self.sec_total, False, False
        now = time.time()
        self.elapsed = int(now - self._start_time)
        over = self.elapsed >= self.sec_total
        if over:
            self.done = True
            self.elapsed = self.sec_total
        return self.elapsed, self.sec_total, self.done, False

    def is_alive(self):
        return not self.done


# ---------------------------------------------------------------------------
# Mindmap geometry helpers
# ---------------------------------------------------------------------------
def node_edge_points(n1, n2, scale, offset_x, offset_y):
    """Compute boundary intersection points between two pill-shaped nodes.

    Returns (x1, y1, x2, y2) on the respective node edges along the line
    connecting the two node centers.
    """
    hw1, hh1 = 50 * scale, 15 * scale
    hw2, hh2 = 50 * scale, 15 * scale
    cx1 = n1['x'] * scale + offset_x + hw1
    cy1 = n1['y'] * scale + offset_y + hh1
    cx2 = n2['x'] * scale + offset_x + hw2
    cy2 = n2['y'] * scale + offset_y + hh2
    dx, dy = cx2 - cx1, cy2 - cy1
    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return cx1, cy1, cx2, cy2
    t1x = hw1 / abs(dx) if abs(dx) > 0.01 else float('inf')
    t1y = hh1 / abs(dy) if abs(dy) > 0.01 else float('inf')
    t1 = min(t1x, t1y)
    x1 = cx1 + t1 * dx
    y1 = cy1 + t1 * dy
    t2x = hw2 / abs(dx) if abs(dx) > 0.01 else float('inf')
    t2y = hh2 / abs(dy) if abs(dy) > 0.01 else float('inf')
    t2 = min(t2x, t2y)
    x2 = cx2 - t2 * dx
    y2 = cy2 - t2 * dy
    return x1, y1, x2, y2


def move_children(mm, parent_id, dx_data, dy_data, moved_ids, depth=0):
    """Recursively move all descendants of parent_id by (dx_data, dy_data)
    in data coords.  Updates node 'x'/'y' in-place and adds child IDs to
    moved_ids set."""
    for edge in mm.get('edges', []):
        if edge['from'] == parent_id:
            child_id = edge['to']
            child = next((n for n in mm.get('nodes', []) if n['id'] == child_id), None)
            if child and child_id not in moved_ids:
                child['x'] += dx_data
                child['y'] += dy_data
                moved_ids.add(child_id)
                if depth < 50:
                    move_children(mm, child_id, dx_data, dy_data, moved_ids, depth + 1)


# ---------------------------------------------------------------------------
# Chamfer tab notebook
# ---------------------------------------------------------------------------
class ChamferNotebook(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._tab_data = []
        self.tab_frames = []
        self.active_idx = 0
        self.bg = '#ffffff'
        self.fg = '#1c1c1e'
        self.active_bg = '#007aff'
        self.inactive_bg = '#f2f2f7'
        self.border = '#c7c7cc'
        self.chamfer = 10

        self.tab_canvas = tk.Canvas(self, height=38, bg=self.bg, highlightthickness=0)
        self.tab_canvas.pack(fill='x', side='top')
        self.tab_canvas.bind('<Button-1>', self._on_tab_click)

        self.content = ttk.Frame(self)
        self.content.pack(fill='both', expand=True)
        self._nb = None  # we manage content manually

    def add(self, child, text='', **kwargs):
        idx = len(self._tab_data)
        self._tab_data.append((text, child))
        child.pack_forget()
        if idx == 0:
            child.pack(fill='both', expand=True, in_=self.content)
        self._redraw_tabs()
        return idx

    def _redraw_tabs(self):
        c = self.tab_canvas
        c.delete('all')
        self.tab_frames = []
        x = 12
        ch = self.chamfer
        h = 34
        for i, (name, _) in enumerate(self._tab_data):
            w = max(len(name) * 9 + 32, 72)
            is_active = (i == self.active_idx)
            fill = self.active_bg if is_active else self.inactive_bg
            pts = [
                x + ch, 4,
                x + w - ch, 4,
                x + w, 4 + ch,
                x + w, 4 + h,
                x, 4 + h,
                x, 4 + ch,
            ]
            tab_id = c.create_polygon(pts, fill=fill, outline=self.border, width=1)
            c.create_text(x + w // 2, 4 + h // 2, text=name, fill=self.fg,
                          font=('SF Pro Text', 9, 'bold' if is_active else ''))
            self.tab_frames.append((tab_id, x, w))
            x += w + 6
        c.config(width=max(x + 12, 200), height=44)

    def _on_tab_click(self, event):
        for i, (tab_id, x, w) in enumerate(self.tab_frames):
            bbox = self.tab_canvas.bbox(tab_id)
            if bbox and bbox[0] <= event.x <= bbox[2] and bbox[1] <= event.y <= bbox[3]:
                self.active_idx = i
                for child in self.content.winfo_children():
                    child.pack_forget()
                self._tab_data[i][1].pack(fill='both', expand=True, in_=self.content)
                self._redraw_tabs()
                break

    def tabs(self):
        return [name for name, _ in self._tab_data]

    def tab(self, idx, option=None):
        return self._tab_data[idx][0]


# ---------------------------------------------------------------------------
# Global style setup (called once after root created)
# ---------------------------------------------------------------------------
def setup_styles(root):
    s = ttk.Style(root)
    try:
        s.theme_use('clam')
    except Exception:
        pass

    glass_bg = '#f5f5f7'
    glass_white = '#ffffff'
    glass_blue = '#007aff'
    glass_green = '#34c759'
    glass_red = '#ff3b30'
    glass_orange = '#ff9500'
    glass_grey = '#8e8e93'
    glass_light_grey = '#e5e5ea'

    s.configure('TFrame', background=glass_bg)
    s.configure('TLabel', background=glass_bg, font=('SF Pro Text', 9))
    s.configure('TLabelframe', background=glass_bg, font=('SF Pro Text', 9, 'bold'))
    s.configure('TLabelframe.Label', background=glass_bg, font=('SF Pro Text', 9, 'bold'))
    s.configure('TButton', font=('SF Pro Text', 9), padding=(8, 4))
    s.configure('TEntry', font=('SF Pro Text', 9), padding=4)
    s.configure('TCombobox', font=('SF Pro Text', 9), padding=4)
    s.configure('TNotebook', background=glass_bg, tabmargins=[8, 8, 8, 0])
    s.configure('TNotebook.Tab', font=('SF Pro Text', 9), padding=(12, 6))
    s.configure('Treeview', font=('SF Pro Text', 9), rowheight=24,
                background=glass_white, fieldbackground=glass_white)
    s.configure('Treeview.Heading', font=('SF Pro Text', 8, 'bold'),
                background=glass_light_grey)
    s.configure('TScrollbar', background=glass_bg, troughcolor=glass_light_grey, width=8)
    s.configure('TCheckbutton', background=glass_bg, font=('SF Pro Text', 9))
    s.configure('TPanedwindow', background=glass_bg)

    s.configure('Primary.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Primary.TButton',
          background=[('active', '#0062cc'), ('!disabled', glass_blue), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Accent.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Accent.TButton',
          background=[('active', '#28a745'), ('!disabled', glass_green), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Danger.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Danger.TButton',
          background=[('active', '#d93025'), ('!disabled', glass_red), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Card.TButton', font=('SF Pro Text', 8), padding=(6, 3))
    s.map('Card.TButton',
          background=[('active', '#e5e5ea'), ('!disabled', glass_white)],
          foreground=[('!disabled', '#1c1c1e')])

    s.configure('Header.TLabel', font=('SF Pro Display', 13, 'bold'), background=glass_bg)
    s.configure('CardTitle.TLabel', font=('SF Pro Text', 9, 'bold'), background=glass_bg)

    s.configure('Green.Horizontal', background=glass_green, troughcolor=glass_light_grey)
    s.configure('Yellow.Horizontal', background=glass_orange, troughcolor=glass_light_grey)
    s.configure('Red.Horizontal', background=glass_red, troughcolor=glass_light_grey)

    s.configure('Card.TLabelframe', background=glass_white, relief='flat', borderwidth=0)
    s.configure('Card.TLabelframe.Label', background=glass_bg, font=('SF Pro Text', 8, 'bold'))


def apply_light_theme():
    s = ttk.Style()
    glass_bg = '#f5f5f7'
    glass_white = '#ffffff'
    glass_blue = '#007aff'
    glass_green = '#34c759'
    glass_red = '#ff3b30'
    glass_orange = '#ff9500'
    glass_grey = '#8e8e93'
    glass_light_grey = '#e5e5ea'

    s.configure('TFrame', background=glass_bg)
    s.configure('TLabel', background=glass_bg, font=('SF Pro Text', 9))
    s.configure('TLabelframe', background=glass_bg, font=('SF Pro Text', 9, 'bold'))
    s.configure('TLabelframe.Label', background=glass_bg, font=('SF Pro Text', 9, 'bold'))
    s.configure('TButton', font=('SF Pro Text', 9), padding=(8, 4))
    s.configure('TEntry', font=('SF Pro Text', 9), padding=4)
    s.configure('TCombobox', font=('SF Pro Text', 9), padding=4)
    s.configure('TNotebook', background=glass_bg, tabmargins=[8, 8, 8, 0])
    s.configure('TNotebook.Tab', font=('SF Pro Text', 9), padding=(12, 6))
    s.configure('Treeview', font=('SF Pro Text', 9), rowheight=24,
                background=glass_white, fieldbackground=glass_white)
    s.configure('Treeview.Heading', font=('SF Pro Text', 8, 'bold'),
                background=glass_light_grey)
    s.configure('TScrollbar', background=glass_bg, troughcolor=glass_light_grey, width=8)
    s.configure('TCheckbutton', background=glass_bg, font=('SF Pro Text', 9))
    s.configure('TPanedwindow', background=glass_bg)
    s.configure('Horizontal.TScale', background=glass_bg, troughcolor=glass_light_grey)
    s.configure('Vertical.TScale', background=glass_bg, troughcolor=glass_light_grey)

    s.configure('Primary.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Primary.TButton',
          background=[('active', '#0062cc'), ('!disabled', glass_blue), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Accent.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Accent.TButton',
          background=[('active', '#28a745'), ('!disabled', glass_green), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Danger.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Danger.TButton',
          background=[('active', '#d93025'), ('!disabled', glass_red), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Card.TButton', font=('SF Pro Text', 8), padding=(6, 3))
    s.map('Card.TButton',
          background=[('active', '#e5e5ea'), ('!disabled', glass_white)],
          foreground=[('!disabled', '#1c1c1e')])

    s.configure('Header.TLabel', font=('SF Pro Display', 13, 'bold'), background=glass_bg)
    s.configure('CardTitle.TLabel', font=('SF Pro Text', 9, 'bold'), background=glass_bg)

    s.configure('Green.Horizontal', background=glass_green, troughcolor=glass_light_grey)
    s.configure('Yellow.Horizontal', background=glass_orange, troughcolor=glass_light_grey)
    s.configure('Red.Horizontal', background=glass_red, troughcolor=glass_light_grey)

    s.configure('Card.TLabelframe', background=glass_white, relief='flat', borderwidth=0)
    s.configure('Card.TLabelframe.Label', background=glass_bg, font=('SF Pro Text', 8, 'bold'))


def apply_dark_theme():
    s = ttk.Style()
    glass_bg = '#1c1c1e'
    glass_white = '#2c2c2e'
    glass_blue = '#0a84ff'
    glass_green = '#30d158'
    glass_red = '#ff453a'
    glass_orange = '#ff9f0a'
    glass_grey = '#8e8e93'
    glass_light_grey = '#3a3a3c'

    s.configure('TFrame', background=glass_bg)
    s.configure('TLabel', background=glass_bg, font=('SF Pro Text', 9))
    s.configure('TLabelframe', background=glass_bg, font=('SF Pro Text', 9, 'bold'))
    s.configure('TLabelframe.Label', background=glass_bg, font=('SF Pro Text', 9, 'bold'))
    s.configure('TButton', font=('SF Pro Text', 9), padding=(8, 4))
    s.configure('TEntry', font=('SF Pro Text', 9), padding=4)
    s.configure('TCombobox', font=('SF Pro Text', 9), padding=4)
    s.configure('TNotebook', background=glass_bg, tabmargins=[8, 8, 8, 0])
    s.configure('TNotebook.Tab', font=('SF Pro Text', 9), padding=(12, 6))
    s.configure('Treeview', font=('SF Pro Text', 9), rowheight=24,
                background=glass_white, fieldbackground=glass_white)
    s.configure('Treeview.Heading', font=('SF Pro Text', 8, 'bold'),
                background=glass_light_grey)
    s.configure('TScrollbar', background=glass_bg, troughcolor=glass_light_grey, width=8)
    s.configure('TCheckbutton', background=glass_bg, font=('SF Pro Text', 9))
    s.configure('TPanedwindow', background=glass_bg)
    s.configure('Horizontal.TScale', background=glass_bg, troughcolor=glass_light_grey)
    s.configure('Vertical.TScale', background=glass_bg, troughcolor=glass_light_grey)

    s.configure('Primary.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Primary.TButton',
          background=[('active', '#0062cc'), ('!disabled', glass_blue), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Accent.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Accent.TButton',
          background=[('active', '#28a745'), ('!disabled', glass_green), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Danger.TButton', font=('SF Pro Text', 9, 'bold'), padding=(10, 5))
    s.map('Danger.TButton',
          background=[('active', '#d93025'), ('!disabled', glass_red), ('disabled', glass_light_grey)],
          foreground=[('!disabled', 'white'), ('disabled', glass_grey)])

    s.configure('Card.TButton', font=('SF Pro Text', 8), padding=(6, 3))
    s.map('Card.TButton',
          background=[('active', '#3a3a3c'), ('!disabled', glass_white)],
          foreground=[('!disabled', '#f5f5f7')])

    s.configure('Header.TLabel', font=('SF Pro Display', 13, 'bold'), background=glass_bg)
    s.configure('CardTitle.TLabel', font=('SF Pro Text', 9, 'bold'), background=glass_bg)

    s.configure('Green.Horizontal', background=glass_green, troughcolor=glass_light_grey)
    s.configure('Yellow.Horizontal', background=glass_orange, troughcolor=glass_light_grey)
    s.configure('Red.Horizontal', background=glass_red, troughcolor=glass_light_grey)

    s.configure('Card.TLabelframe', background=glass_white, relief='flat', borderwidth=0)
    s.configure('Card.TLabelframe.Label', background=glass_bg, font=('SF Pro Text', 8, 'bold'))
