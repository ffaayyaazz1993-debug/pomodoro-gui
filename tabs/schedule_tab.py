"""ScheduleTab — schtasks-based recurring pomodoros."""
import os
import time
import uuid
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pomodoro_common import load, save, get_current_project, PROG


class ScheduleTab(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='When:').pack(side='left')
        self.sched_when = ttk.Entry(top, width=22)
        self.sched_when.insert(0, 'Every day 09:00')
        self.sched_when.pack(side='left', padx=4)
        ttk.Label(top, text='Min:').pack(side='left')
        self.sched_min = ttk.Entry(top, width=5, justify='center')
        self.sched_min.insert(0, '25')
        self.sched_min.pack(side='left', padx=4)
        ttk.Label(top, text='Label:').pack(side='left', padx=(10, 0))
        self.sched_lbl = ttk.Entry(top, width=20)
        self.sched_lbl.insert(0, 'Pomodoro')
        self.sched_lbl.pack(side='left', padx=4)
        ttk.Button(top, text='+ Add schedule', command=self._add, style='Primary.TButton').pack(side='left', padx=8)

        ttk.Separator(self).pack(fill='x', padx=8)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill='both', expand=True, padx=8, pady=4)
        cols = ('id', 'spec', 'min', 'label', 'taskname')
        self.sched_tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='browse')
        self.sched_tree.heading('id', text='ID')
        self.sched_tree.heading('spec', text='Schedule')
        self.sched_tree.heading('min', text='Min')
        self.sched_tree.heading('label', text='Label')
        self.sched_tree.heading('taskname', text='Task name')
        self.sched_tree.column('id', width=70, anchor='center')
        self.sched_tree.column('spec', width=180, anchor='w')
        self.sched_tree.column('min', width=50, anchor='center')
        self.sched_tree.column('label', width=140, anchor='w')
        self.sched_tree.column('taskname', width=200, anchor='w')
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self.sched_tree.yview)
        self.sched_tree.configure(yscrollcommand=vsb.set)
        self.sched_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        bot = ttk.Frame(self)
        bot.pack(fill='x', padx=8, pady=4)
        ttk.Button(bot, text='\u2715 Cancel selected', command=self._remove, style='Danger.TButton').pack(side='left')
        ttk.Button(bot, text='Refresh', command=self.refresh).pack(side='left', padx=8)
        self.sched_count = ttk.Label(bot, text='0 schedules')
        self.sched_count.pack(side='right')

        self.refresh()

    def _add(self):
        when = self.sched_when.get().strip()
        try:
            mins = int(self.sched_min.get())
        except ValueError:
            messagebox.showerror('Schedule', 'Minutes must be a number.')
            return
        if mins < 1:
            messagebox.showerror('Schedule', 'Minutes must be >= 1.')
            return
        label = self.sched_lbl.get().strip() or when
        data = load()
        project = get_current_project(data)
        uid = str(uuid.uuid4())[:8]
        name = 'HermesPomodoro_' + uid
        task_cmd = 'pythonw.exe "%s" run-only %d "%s"' % (PROG.replace('\\', '/'), mins, label.replace('"', ''))
        args = ['schtasks', '/Create', '/SC', 'DAILY', '/TN', name, '/TR', task_cmd]
        txt = when.strip().lower()
        sc = 'DAILY'; mo = None; st = None
        if txt.startswith('every day'):
            rest = when[9:].strip()
            if ':' in rest: st = rest
        elif txt.startswith('every monday'):
            sc = 'WEEKLY'; mo = 'MON'; rest = when[12:].strip()
            if ':' in rest: st = rest
        elif txt.startswith('every tuesday'):
            sc = 'WEEKLY'; mo = 'TUE'; rest = when[13:].strip()
            if ':' in rest: st = rest
        elif txt.startswith('every wednesday'):
            sc = 'WEEKLY'; mo = 'WED'; rest = when[14:].strip()
            if ':' in rest: st = rest
        elif txt.startswith('every thursday'):
            sc = 'WEEKLY'; mo = 'THU'; rest = when[15:].strip()
            if ':' in rest: st = rest
        elif txt.startswith('every friday'):
            sc = 'WEEKLY'; mo = 'FRI'; rest = when[14:].strip()
            if ':' in rest: st = rest
        elif txt.startswith('every saturday'):
            sc = 'WEEKLY'; mo = 'SAT'; rest = when[15:].strip()
            if ':' in rest: st = rest
        elif txt.startswith('every sunday'):
            sc = 'WEEKLY'; mo = 'SUN'; rest = when[14:].strip()
            if ':' in rest: st = rest
        elif 'hour' in txt:
            sc = 'HOURLY'
            for p in when.split():
                if p.isdigit(): mo = int(p); break
        elif 'min' in txt:
            sc = 'MINUTE'
            for p in when.split():
                if p.isdigit(): mo = int(p); break
        elif ':' in when:
            st = when; sc = 'DAILY'
        else:
            messagebox.showerror('Schedule', 'Cannot parse: ' + when +
                                 '\nUse e.g. "Every day 09:00", "Every Monday 10:30", "Every 2 hours".')
            return
        if mo:
            args += ['/MO', str(mo)]
        if st:
            args += ['/ST', st]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                messagebox.showerror('schtasks', 'Create failed:\n' + r.stderr.strip() + '\n' + r.stdout.strip())
                return
        except Exception as e:
            messagebox.showerror('schtasks', 'Error: ' + str(e))
            return
        entry = {'id': uid, 'spec': when, 'minutes': mins, 'label': label,
                 'taskname': name, 'created': time.strftime('%Y-%m-%dT%H:%M:%S')}
        project['schedules'].append(entry)
        save(data)
        self.refresh()

    def _remove(self):
        sel = self.sched_tree.selection()
        if not sel:
            messagebox.showwarning('Cancel', 'Select a schedule first.')
            return
        tid = sel[0]
        data = load()
        project = get_current_project(data)
        found = None
        for s in project.get('schedules', []):
            if s['id'] == tid:
                found = s; break
        if not found:
            messagebox.showerror('Cancel', 'Schedule not found in data.')
            return
        if not messagebox.askyesno('Cancel', 'Cancel "' + found['label'] + '"?'):
            return
        try:
            subprocess.run(['schtasks', '/Delete', '/TN', found['taskname'], '/F'],
                           capture_output=True, text=True, timeout=30)
        except Exception as e:
            messagebox.showerror('schtasks', 'Delete error: ' + str(e))
        project['schedules'] = [s for s in project.get('schedules', []) if s['id'] != tid]
        save(data)
        self.refresh()

    def refresh(self):
        for row in self.sched_tree.get_children():
            self.sched_tree.delete(row)
        project = self.controller.current_project()
        if not project:
            return
        for s in project.get('schedules', []):
            self.sched_tree.insert('', 'end', iid=s['id'],
                                   values=(s['id'], s['spec'], s['minutes'], s['label'], s['taskname']))
        self.sched_count.config(text='%d schedules' % len(project.get('schedules', [])))
