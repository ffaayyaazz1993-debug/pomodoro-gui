"""PlannerTab — weekly grid + task pool for scheduling."""
import time
import uuid
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pomodoro_common import load, save, all_todos


class PlannerTab(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.planner_week_offset = 0
        self._build()

    def _build(self):
        header = ttk.Frame(self)
        header.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Button(header, text='\u25c0', style='Card.TButton',
                    command=lambda: self._change_week(-1)).pack(side='left', padx=4)
        self.planner_week_label = ttk.Label(header, font=('SF Pro Text', 11, 'bold'))
        self.planner_week_label.pack(side='left', padx=8)
        ttk.Button(header, text='\u25b6', style='Card.TButton',
                    command=lambda: self._change_week(1)).pack(side='left', padx=4)
        ttk.Button(header, text='Today', style='Card.TButton',
                    command=self._go_today).pack(side='left', padx=8)

        self.planner_canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg='#ffffff')
        planner_scroll = ttk.Scrollbar(self, orient='horizontal', command=self.planner_canvas.xview)
        self.planner_inner = ttk.Frame(self.planner_canvas)
        self.planner_canvas.create_window((0, 0), window=self.planner_inner, anchor='nw', tags='planner_inner')
        self.planner_canvas.configure(xscrollcommand=planner_scroll.set)
        self.planner_canvas.bind('<Configure>', lambda e: self.planner_canvas.itemconfig('planner_inner', width=e.width))
        self.planner_inner.bind('<Configure>', lambda e: self.planner_canvas.configure(
            scrollregion=self.planner_canvas.bbox('all')))
        self.planner_canvas.pack(side='top', fill='both', expand=True, padx=(8, 0), pady=4)
        planner_scroll.pack(side='bottom', fill='x', padx=(8, 0))

        pool_frame = ttk.LabelFrame(self, text='Task Pool (drag to schedule)', padding=4)
        pool_frame.pack(fill='x', padx=8, pady=(0, 4))
        self.planner_pool_canvas = tk.Canvas(pool_frame, height=60, borderwidth=0, highlightthickness=0, bg='#f8f8f8')
        self.planner_pool_inner = ttk.Frame(self.planner_pool_canvas)
        self.planner_pool_canvas.create_window((0, 0), window=self.planner_pool_inner, anchor='nw')
        self.planner_pool_inner.bind('<Configure>', lambda e: self.planner_pool_canvas.configure(
            scrollregion=self.planner_pool_canvas.bbox('all')))
        self.planner_pool_canvas.pack(fill='x')

        self.refresh()

    def _change_week(self, delta):
        self.planner_week_offset += delta
        self.refresh()

    def _go_today(self):
        self.planner_week_offset = 0
        self.refresh()

    def refresh(self):
        today = dt.date.today()
        start_of_week = today - dt.timedelta(days=today.weekday()) + dt.timedelta(weeks=self.planner_week_offset)
        week_days = [start_of_week + dt.timedelta(days=i) for i in range(7)]
        week_label = f"{week_days[0].strftime('%b %d')} \u2014 {week_days[6].strftime('%b %d, %Y')}"
        self.planner_week_label.config(text=week_label)

        for child in self.planner_inner.winfo_children():
            child.destroy()
        for child in self.planner_pool_inner.winfo_children():
            child.destroy()

        ttk.Label(self.planner_inner, text='Time', width=8).grid(row=0, column=0, padx=1, pady=1)
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day in enumerate(week_days):
            is_today = (day == today)
            lbl = ttk.Label(self.planner_inner,
                            text=f"{days[i]}\n{day.strftime('%d')}",
                            font=('SF Pro Text', 8, 'bold' if is_today else ''),
                            foreground='#007aff' if is_today else '#1c1c1e',
                            anchor='center', width=12)
            lbl.grid(row=0, column=i+1, padx=1, pady=1)

        for hour in range(8, 23):
            row = hour - 7
            time_str = f"{hour:02d}:00"
            ttk.Label(self.planner_inner, text=time_str, font=('SF Pro Text', 7),
                      foreground='#8e8e93', anchor='e', width=8).grid(row=row, column=0, padx=1, pady=1)
            for day_idx in range(7):
                cell = ttk.Frame(self.planner_inner, relief='solid', borderwidth=0,
                                  style='Card.TLabelframe', width=100, height=40)
                cell.grid(row=row, column=day_idx+1, padx=1, pady=1, sticky='nsew')
                cell.grid_propagate(False)
                cell.bind('<Button-1>', lambda e, h=hour, d=day_idx: self._add_to_slot(h, d, week_days[d]))

        project = self.controller.current_project()
        if project:
            scheduled = set()
            for todo in project.get('todos', []):
                planned = todo.get('planned_day')
                planned_hour = todo.get('planned_hour')
                if planned is not None and planned_hour is not None:
                    try:
                        pdate = dt.date.fromisoformat(planned)
                        if pdate in week_days:
                            day_idx = week_days.index(pdate)
                            row = planned_hour - 7
                            if 8 <= planned_hour <= 22:
                                lbl = ttk.Label(self.planner_inner,
                                                  text=todo['desc'][:15],
                                                  font=('SF Pro Text', 7),
                                                  background='#007aff', foreground='white',
                                                  anchor='center', padx=2)
                                lbl.grid(row=row, column=day_idx+1, padx=1, pady=1, sticky='nsew')
                                scheduled.add(todo['id'])
                    except Exception:
                        pass

            for todo in project.get('todos', []):
                if todo['id'] not in scheduled and not todo.get('done', False):
                    btn = ttk.Button(self.planner_pool_inner, text=todo['desc'][:25],
                                      style='Card.TButton',
                                      command=lambda t=todo: self._schedule_task(t))
                    btn.pack(side='left', padx=2, pady=4)

    def _add_to_slot(self, hour, day_idx, date):
        desc = simpledialog.askstring('New Task', 'Task description:', parent=self)
        if not desc:
            return
        data = load()
        from pomodoro_common import get_current_project
        project = get_current_project(data)
        todo = {
            'id': str(uuid.uuid4())[:8],
            'desc': desc,
            'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'done': False,
            'priority': 2,
            'pomodoros': 0,
            'last_done': '',
            'notes': '',
            'planned_day': date.isoformat(),
            'planned_hour': hour
        }
        project['todos'].append(todo)
        save(data)
        self.refresh()

    def _schedule_task(self, todo):
        date_str = simpledialog.askstring('Schedule Task', 'Date (YYYY-MM-DD):',
                                           parent=self, initialvalue=dt.date.today().isoformat())
        if not date_str:
            return
        hour_str = simpledialog.askstring('Schedule Task', 'Hour (8-22):',
                                           parent=self, initialvalue='9')
        if not hour_str:
            return
        try:
            planned_date = dt.date.fromisoformat(date_str.strip())
            planned_hour = int(hour_str.strip())
            if planned_hour < 8 or planned_hour > 22:
                raise ValueError
        except Exception:
            messagebox.showerror('Error', 'Invalid date or hour.')
            return
        data = load()
        for t in all_todos(data):
            if t['id'] == todo['id']:
                t['planned_day'] = planned_date.isoformat()
                t['planned_hour'] = planned_hour
                break
        save(data)
        self.refresh()
