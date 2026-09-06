"""TodoTab — Eisenhower-priority todo list with per-task timer cards."""
import os
import time
import uuid
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from pomodoro_common import (
    Q1, Q2, Q3, Q4, PQ_LABEL, load, save, get_current_project, all_todos,
    fire_sound, toast, TimerRunner,
)


class TodoTab(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._task_cards = {}
        self.extra_disp = {}
        self._build()

    def _build(self):
        # project selector
        proj_bar = ttk.Frame(self)
        proj_bar.pack(fill='x', pady=(8, 4))
        ttk.Label(proj_bar, text='Project:').pack(side='left', padx=(8, 4))
        self.project_cb = ttk.Combobox(proj_bar, textvariable=self.controller.project_var,
                                        width=20, state='readonly')
        self.project_cb.pack(side='left', padx=4)
        self.project_cb.bind('<<ComboboxSelected>>', self._on_project_selected)
        ttk.Button(proj_bar, text='+', style='Primary.TButton',
                    command=self._add_project).pack(side='left', padx=2)
        ttk.Button(proj_bar, text='-', style='Danger.TButton',
                    command=self._remove_project).pack(side='left', padx=2)
        ttk.Separator(self).pack(fill='x')

        # add task bar
        top = ttk.Frame(self)
        top.pack(fill='x', pady=(8, 4))
        ttk.Label(top, text='Task:').pack(side='left', padx=(8, 0))
        self.todo_input_field = ttk.Entry(top)
        self.todo_input_field.pack(side='left', fill='x', expand=True, padx=4)
        ttk.Label(top, text='Q:').pack(side='left', padx=(4, 0))
        self.todo_q = ttk.Combobox(top, values=[1, 2, 3, 4], width=3, state='readonly')
        self.todo_q.pack(side='left', padx=2)
        self.todo_q.set(2)
        ttk.Label(top, text='Cat:').pack(side='left', padx=(4, 0))
        self.todo_cat = ttk.Combobox(top, width=12)
        self.todo_cat.pack(side='left', padx=2)
        self.todo_cat.set('')
        self.todo_cat.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='+', style='Primary.TButton',
                    command=self._add_category).pack(side='left', padx=2)
        ttk.Button(top, text='+ Add', command=self._todo_add,
                    style='Primary.TButton').pack(side='left', padx=(4, 8))
        ttk.Separator(self).pack(fill='x')

        # scrollable task cards
        self.tasks_canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg='#ffffff')
        self.tasks_scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.tasks_canvas.yview)
        self.tasks_inner = ttk.Frame(self.tasks_canvas)
        self.tasks_canvas.create_window((0, 0), window=self.tasks_inner, anchor='nw', tags='inner')
        self.tasks_canvas.configure(yscrollcommand=self.tasks_scrollbar.set)
        self.tasks_canvas.bind('<Configure>', lambda e: self.tasks_canvas.itemconfig('inner', width=e.width))
        self.tasks_inner.bind('<Configure>', lambda e: self.tasks_canvas.configure(
            scrollregion=self.tasks_canvas.bbox('all')))
        self.tasks_canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.tasks_canvas.bind('<Button-4>', self._on_mousewheel)
        self.tasks_canvas.bind('<Button-5>', self._on_mousewheel)
        self.tasks_canvas.pack(side='left', fill='both', expand=True, pady=(4, 0))
        self.tasks_scrollbar.pack(side='right', fill='y', pady=(4, 0))

        # bottom bar
        bot = ttk.Frame(self)
        bot.pack(fill='x', padx=8, pady=(2, 4))
        self.todo_count = ttk.Label(bot, text='0 todos')
        self.todo_count.pack(side='right')

        self._refresh_projects()
        self.refresh()

    def _on_mousewheel(self, event):
        if event.num == 4: incr = -1
        elif event.num == 5: incr = 1
        else: incr = -1 if event.delta > 0 else 1
        self.tasks_canvas.yview_scroll(incr, 'units')

    def _refresh_projects(self):
        names, current_name = self.controller.refresh_projects()
        self.project_cb['values'] = names
        if current_name:
            self.controller.project_var.set(current_name)

    def _on_project_selected(self, event=None):
        self.controller.set_project(self.controller.project_var.get())
        self.refresh()

    def _add_project(self):
        dialog = tk.Toplevel(self)
        dialog.title('New Project')
        dialog.geometry('300x120')
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text='Project name:').pack(padx=10, pady=(10, 4))
        name_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        entry.pack(padx=10); entry.focus()
        def do():
            name = name_var.get().strip()
            if name:
                self.controller.add_project(name)
                self._refresh_projects()
                self.refresh()
            dialog.destroy()
        ttk.Button(dialog, text='Create', command=do).pack(pady=10)
        entry.bind('<Return>', lambda e: do())

    def _remove_project(self):
        data = load()
        if len(data['projects']) <= 1:
            messagebox.showwarning('Remove', 'Cannot remove the last project.')
            return
        pid = data.get('current_project', 'default')
        pname = self.controller.project_var.get()
        if not messagebox.askyesno('Remove', f'Delete project "{pname}" and all its tasks?'):
            return
        if self.controller.remove_project(pid):
            self._refresh_projects()
            self.refresh()

    def _add_category(self):
        dialog = tk.Toplevel(self)
        dialog.title('New Folder')
        dialog.geometry('300x120')
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text='Folder name:').pack(padx=10, pady=(10, 4))
        name_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        entry.pack(padx=10); entry.focus()
        def do():
            name = name_var.get().strip()
            if name:
                vals = list(self.todo_cat['values']) if self.todo_cat['values'] else []
                if name not in vals:
                    vals.append(name)
                    self.todo_cat['values'] = sorted(vals)
                self.todo_cat.set(name)
                dialog.destroy()
        entry.bind('<Return>', lambda e: do())
        ttk.Button(dialog, text='Create', command=do).pack(pady=10)

    def _todo_add(self):
        desc = self.todo_input_field.get().strip()
        if not desc:
            messagebox.showwarning('Add todo', 'Enter a task description.')
            return
        q = int(self.todo_q.get())
        cat = self.todo_cat.get().strip()
        data = load()
        project = get_current_project(data)
        todo = {'id': str(uuid.uuid4())[:8], 'desc': desc,
                'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'done': False, 'priority': q, 'pomodoros': 0,
                'last_done': '', 'notes': '', 'category': cat}
        project['todos'].append(todo)
        save(data)
        self.todo_input_field.delete(0, 'end')
        self.refresh()

    def refresh(self):
        for child in self.tasks_inner.winfo_children():
            child.destroy()
        self._task_cards.clear()
        self.extra_disp.clear()

        project = self.controller.current_project()
        if not project:
            return
        todos = project.get('todos', [])

        def key(t):
            p = t.get('priority')
            pnum = p if p in (Q1, Q2, Q3, Q4) else 99
            try:
                ts = time.mktime(time.strptime(t['created'], '%Y-%m-%dT%H:%M:%S'))
            except Exception:
                ts = 0.0
            return (pnum, -ts)

        todos_sorted = sorted(todos, key=key)
        filter_cat = self.todo_cat.get().strip()
        if filter_cat:
            todos_sorted = [t for t in todos_sorted if (t.get('category', '').strip() or 'No Category') == filter_cat]

        cats = {}
        for t in todos_sorted:
            c = t.get('category', '').strip() or 'No Category'
            cats.setdefault(c, []).append(t)

        for cat, cat_todos in sorted(cats.items()):
            cat_frame = ttk.LabelFrame(self.tasks_inner,
                                        text='\U0001f4c1 %s (%d)' % (cat, len(cat_todos)),
                                        padding=4, style='Card.TLabelframe')
            cat_frame.pack(fill='x', padx=4, pady=3)
            cat_frame._collapsed = False
            cat_inner = ttk.Frame(cat_frame)
            cat_inner.pack(fill='x')

            def toggle(cat_f=cat_frame, ci=cat_inner, cnt=len(cat_todos), cn=cat):
                if cat_f._collapsed:
                    ci.pack(fill='x')
                    cat_f.config(text='\U0001f4c1 %s (%d)' % (cn, cnt))
                    cat_f._collapsed = False
                else:
                    ci.pack_forget()
                    cat_f.config(text='\u25b6 %s (%d) [collapsed]' % (cn, cnt))
                    cat_f._collapsed = True

            cat_frame.bind('<Button-1>', lambda e, t=toggle: t())

            for t in cat_todos:
                self._build_task_card(t, cat_inner)

        cats_list = sorted(set(t.get('category', '').strip() for t in todos if t.get('category', '').strip()))
        self.todo_cat['values'] = [''] + cats_list

        cnt = len([t for t in todos if not t.get('done')])
        self.todo_count.config(text='%d open / %d total' % (cnt, len(todos)))

    def _build_task_card(self, todo, parent=None):
        if parent is None:
            parent = self.tasks_inner
        tid = todo['id']
        desc = todo['desc']
        pomo = todo.get('pomodoros', 0)
        p = todo.get('priority')
        label = PQ_LABEL.get(p, '') if p else ''

        card = ttk.LabelFrame(parent,
                              text='%s \u2014 %s (pomodoros: %d)' % (tid, desc, pomo),
                              padding=4, style='Card.TLabelframe')
        card.pack(fill='x', padx=4, pady=3)
        card.value = {}

        info = ttk.Frame(card)
        info.pack(fill='x')
        priority_var = tk.StringVar(value=label if label else 'Q?')
        priority_cb = ttk.Combobox(info, textvariable=priority_var,
                                    values=list(PQ_LABEL.values()),
                                    width=8, state='readonly')
        priority_cb.pack(side='left', padx=(0, 4))
        priority_cb.bind('<<ComboboxSelected>>', lambda e: self._set_priority(tid, priority_var.get()))
        card.value['priority_cb'] = priority_cb
        ttk.Label(info, text='Created: %s' % todo['created'][:10],
                   foreground='grey').pack(side='left', padx=4)
        last_done = todo.get('last_done', '')[:16]
        ttk.Label(info, text='Last: %s' % last_done if last_done else 'Last: \u2014',
                   foreground='grey').pack(side='left', padx=4)
        ttk.Label(info, text='Pomos: %d' % pomo,
                   foreground='#059669', font=('SF Pro Text', 8, 'bold')).pack(side='left', padx=(8, 4))
        ttk.Button(info, text='\u2713', style='Accent.TButton',
                    command=lambda: self._todo_done(tid)).pack(side='right', padx=2)
        ttk.Button(info, text='\u2715', style='Danger.TButton',
                    command=lambda: self._todo_remove(tid)).pack(side='right', padx=2)

        timer_row = ttk.Frame(card)
        timer_row.pack(fill='x', pady=(2, 0))
        time_lbl = ttk.Label(timer_row, text='00:00 / 25:00', font=('Consolas', 11))
        time_lbl.pack(side='left', padx=(0, 6))
        prog = ttk.Progressbar(timer_row, orient='horizontal', mode='determinate', length=200)
        prog.pack(side='left', padx=(0, 4))
        mins_var = tk.StringVar(value='25')
        mins_cb = ttk.Combobox(timer_row, textvariable=mins_var,
                                values=[5, 10, 15, 20, 25, 30, 45, 60],
                                width=3, state='readonly')
        mins_cb.pack(side='left', padx=2)
        mins_cb.set(25)
        start_btn = ttk.Button(timer_row, text='\u25b6', style='Primary.TButton',
                                command=lambda: self._panel_start_any(tid))
        start_btn.pack(side='left', padx=2)
        pause_btn = ttk.Button(timer_row, text='\u23f8',
                                command=lambda: self.controller.card_pause(tid))
        pause_btn.pack(side='left', padx=2)
        stop_btn = ttk.Button(timer_row, text='\u25a0', style='Danger.TButton',
                               command=lambda: self.controller.card_stop(tid))
        stop_btn.pack(side='left', padx=2)
        sound_var = tk.BooleanVar(value=self.controller.sound_on.get())
        ttk.Checkbutton(timer_row, text='\u266a', variable=sound_var).pack(side='left', padx=(4, 2))
        ttk.Button(timer_row, text='+1', style='Accent.TButton',
                    command=lambda: self.controller.card_skip(tid)).pack(side='left', padx=2)

        sub_frame = ttk.Frame(card)
        sub_frame.pack(fill='x', pady=(2, 0))
        sub_var = tk.StringVar()
        sub_entry = ttk.Entry(sub_frame, textvariable=sub_var)
        sub_entry.pack(side='left', fill='x', expand=True, padx=(0, 4))
        sub_entry.bind('<Return>', lambda e: self._add_subtask(tid, sub_var))
        ttk.Button(sub_frame, text='+ Sub', style='Card.TButton',
                    command=lambda: self._add_subtask(tid, sub_var)).pack(side='left')

        subs = todo.get('subtasks', [])
        if subs:
            subs_frame = ttk.Frame(card)
            subs_frame.pack(fill='x', pady=(2, 0))
            for sub in subs:
                self._build_subtask_row(tid, sub, subs_frame)

        self._build_quran_meta(card, tid, todo)

        extra = todo.get('extra_input', {})
        if extra.get('type') or extra.get('value') or extra.get('options'):
            self._build_extra_input(card, tid, extra)

        card.value.update({
            'time_lbl': time_lbl, 'prog': prog, 'mins_var': mins_var,
            'start_btn': start_btn, 'pause_btn': pause_btn,
            'sound_var': sound_var, 'mins_cb': mins_cb
        })
        self._task_cards[tid] = card
        return card

    def _build_extra_input(self, card, tid, extra):
        extra_frame = ttk.Frame(card)
        extra_frame.pack(fill='x', pady=(4, 0))

        type_row = ttk.Frame(extra_frame)
        type_row.pack(fill='x')
        ttk.Label(type_row, text='Type:').pack(side='left', padx=(0, 4))
        extra_type_var = tk.StringVar(value=extra.get('type', 'Text'))
        extra_type_cb = ttk.Combobox(type_row, textvariable=extra_type_var,
                                      values=['Text', 'Number', 'Dropdown'], width=10, state='readonly')
        extra_type_cb.pack(side='left', padx=2)
        ttk.Button(type_row, text='\u2715', style='Danger.TButton',
                    command=lambda: self._clear_extra_input(tid)).pack(side='right', padx=2)

        input_row = ttk.Frame(extra_frame)
        input_row.pack(fill='x', pady=(2, 0))
        extra_field = ttk.Entry(input_row)
        extra_field.pack(side='left', fill='x', expand=True, padx=(0, 4))
        extra_field.insert(0, extra.get('value', ''))
        ttk.Button(input_row, text='+ Add', style='Primary.TButton',
                    command=lambda: self._add_extra_to_task(tid, extra_field)).pack(side='left', padx=2)
        ttk.Button(input_row, text='Set', style='Card.TButton',
                    command=lambda: self._update_extra_value(tid, extra_field)).pack(side='left', padx=2)

        if extra.get('value'):
            disp = ttk.Label(extra_frame, text=extra['value'],
                             foreground='#007aff', font=('SF Pro Text', 8))
            disp.pack(fill='x', pady=(2, 0))
            self.extra_disp[tid] = disp

        opts_row = ttk.Frame(extra_frame)
        opts_label = ttk.Label(opts_row, text='Options (comma-sep):')
        opts_label.pack(side='left', padx=(0, 4))
        opts_entry = ttk.Entry(opts_row, width=30)
        opts_entry.pack(side='left', fill='x', expand=True, padx=(0, 4))
        opts_entry.insert(0, extra.get('options', ''))
        ttk.Button(opts_row, text='Apply', style='Card.TButton',
                    command=lambda: self._apply_task_extra_opts(tid, extra_field, opts_entry)).pack(side='left')

        def show_hide_opts():
            if extra_type_var.get() == 'Dropdown':
                opts_row.pack(fill='x', pady=(2, 0))
            else:
                opts_row.pack_forget()
            self._save_extra_input_type(tid, extra_type_var.get())

        extra_type_cb.bind('<<ComboboxSelected>>', lambda e: show_hide_opts())
        if extra.get('type') == 'Dropdown':
            opts_row.pack(fill='x', pady=(2, 0))

        def save_extra(*args):
            self._save_extra_input_value(tid, extra_field.get())
        extra_field.bind('<FocusOut>', save_extra)
        extra_field.bind('<Return>', save_extra)

    def _save_extra_input_type(self, tid, typ):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    t.setdefault('extra_input', {})['type'] = typ
                    save(data)
                    return

    def _save_extra_input_value(self, tid, val):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    t.setdefault('extra_input', {})['value'] = val
                    save(data)
                    return

    def _apply_task_extra_opts(self, tid, field, opts_entry):
        opts = opts_entry.get().strip()
        if opts:
            values = [o.strip() for o in opts.split(',') if o.strip()]
            field['values'] = values
            data = load()
            for p in data['projects']:
                for t in p.get('todos', []):
                    if t['id'] == tid:
                        t.setdefault('extra_input', {})['options'] = opts
                        save(data)
                        break

    def _clear_extra_input(self, tid):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    t.pop('extra_input', None)
                    save(data)
                    self.refresh()
                    return

    def _add_extra_to_task(self, tid, field):
        val = field.get().strip()
        if not val:
            return
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    extra = t.setdefault('extra_input', {})
                    prev = extra.get('value', '')
                    extra['value'] = prev + (' | ' + val if prev else val)
                    save(data)
                    field.delete(0, 'end')
                    self._update_extra_display(tid)
                    self.refresh()
                    return

    def _update_extra_value(self, tid, field):
        val = field.get().strip()
        if not val:
            return
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    extra = t.setdefault('extra_input', {})
                    extra['value'] = val
                    save(data)
                    field.delete(0, 'end')
                    self._update_extra_display(tid)
                    self.refresh()
                    return

    def _update_extra_display(self, tid):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    val = t.get('extra_input', {}).get('value', '')
                    if tid in self.extra_disp:
                        if val:
                            self.extra_disp[tid].config(text=val)
                        else:
                            self.extra_disp[tid].destroy()
                            del self.extra_disp[tid]
                    break

    def _add_subtask(self, tid, var):
        desc = var.get().strip()
        if not desc:
            return
        data = load()
        for t in all_todos(data):
            if t['id'] == tid:
                if 'subtasks' not in t:
                    t['subtasks'] = []
                t['subtasks'].append({'id': str(uuid.uuid4())[:6], 'desc': desc, 'done': False})
                break
        save(data)
        var.set('')
        self.refresh()

    def _build_subtask_row(self, parent_tid, sub, frame):
        row = ttk.Frame(frame)
        row.pack(fill='x', padx=(16, 0), pady=1)
        done_var = tk.BooleanVar(value=sub.get('done', False))
        cb = ttk.Checkbutton(row, variable=done_var,
                              command=lambda: self._toggle_subtask(parent_tid, sub['id'], done_var))
        cb.pack(side='left')
        lbl = ttk.Label(row, text=sub['desc'], foreground='grey' if sub.get('done') else '#1c1c1e')
        lbl.pack(side='left', padx=4)
        ttk.Button(row, text='\u2715', style='Card.TButton',
                    command=lambda: self._remove_subtask(parent_tid, sub['id'])).pack(side='right')

    def _toggle_subtask(self, parent_tid, sub_id, var):
        data = load()
        for t in all_todos(data):
            if t['id'] == parent_tid:
                for s in t.get('subtasks', []):
                    if s['id'] == sub_id:
                        s['done'] = var.get()
                        break
                break
        save(data)

    def _remove_subtask(self, parent_tid, sub_id):
        data = load()
        for t in all_todos(data):
            if t['id'] == parent_tid:
                t['subtasks'] = [s for s in t.get('subtasks', []) if s['id'] != sub_id]
                break
        save(data)
        self.refresh()

    def _save_notes(self, tid, text_widget):
        val = text_widget.get('1.0', 'end-1c')
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    t['notes'] = val
                    save(data)
                    return

    def _build_quran_meta(self, card, tid, todo):
        """Surah + Ayat + Notes grouped as a Quran metadata section in the task card."""
        surah_frame = ttk.Frame(card)
        surah_frame.pack(fill='x', pady=(2, 0))
        ttk.Label(surah_frame, text='Surah:').pack(side='left', padx=(0, 4))
        surah_var = tk.StringVar(value=str(todo.get('surah', '')))
        surah_cb = ttk.Combobox(surah_frame, textvariable=surah_var,
                                 values=[str(i) for i in range(1, 115)],
                                 width=5, state='readonly')
        surah_cb.pack(side='left', padx=2)

        ayat_frame = ttk.Frame(card)
        ayat_frame.pack(fill='x', pady=(2, 0))
        ttk.Label(ayat_frame, text='Ayat:').pack(side='left', padx=(0, 4))
        ayat_var = tk.StringVar(value=str(todo.get('ayat', '')))
        ayat_cb = ttk.Combobox(ayat_frame, textvariable=ayat_var,
                                values=[str(i) for i in range(1, self._surah_ayat_count(int(surah_var.get() or 1)) + 1)],
                                width=5, state='readonly')
        ayat_cb.pack(side='left', padx=2)

        # both widgets exist now — bind after
        surah_cb.bind('<<ComboboxSelected>>',
                       lambda e: self._on_surah_changed(tid, surah_var, ayat_cb))
        ayat_cb.bind('<<ComboboxSelected>>',
                      lambda e: self._save_ayat(tid, ayat_var.get()))
        card.value['surah_var'] = surah_var
        card.value['surah_cb'] = surah_cb
        card.value['ayat_var'] = ayat_var
        card.value['ayat_cb'] = ayat_cb

        notes_frame = ttk.Frame(card)
        notes_frame.pack(fill='x', pady=(2, 0))
        notes_text = tk.Text(notes_frame, height=2, width=40,
                             font=('SF Pro Text', 9),
                             bg='#f5f5f5', borderwidth=1, relief='solid',
                             padx=4, pady=2)
        notes_text.pack(fill='x', expand=True)
        notes_text.insert('1.0', todo.get('notes', '') or '')
        notes_text.bind('<FocusOut>', lambda e: self._save_notes(tid, notes_text))
        card.value['notes_text'] = notes_text

    def _save_surah(self, tid, val):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    t['surah'] = val
        save(data)

    # Quran surah -> ayat count (Kufan count, 6236 total)
    SURAH_AYAT = {
        1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
        11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98, 20: 135,
        21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60,
        31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
        41: 54, 42: 53, 43: 89, 44: 59, 45: 59, 46: 35, 47: 38, 48: 29, 49: 14, 50: 45,
        51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29, 58: 22, 59: 24, 60: 13,
        61: 14, 62: 11, 63: 6, 64: 18, 65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44,
        71: 28, 72: 28, 73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
        81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20,
        91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
        101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 4,
        111: 5, 112: 4, 113: 5, 114: 6,
    }

    def _surah_ayat_count(self, surah_num):
        return self.SURAH_AYAT.get(surah_num, 0)

    def _on_surah_changed(self, tid, surah_var, ayat_cb):
        try:
            surah = int(surah_var.get() or 1)
        except Exception:
            surah = 1
        count = self._surah_ayat_count(surah)
        ayat_cb['values'] = [str(i) for i in range(1, count + 1)] if count else []
        # reset ayat if out of range
        try:
            cur_val = ayat_cb.get()
            if cur_val.isdigit() and int(cur_val) > count:
                ayat_cb.set('')
        except Exception:
            pass
        self._save_surah(tid, str(surah))

    def _save_ayat(self, tid, val):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    t['ayat'] = val
        save(data)

    def _set_priority(self, tid, label):
        data = load()
        for t in all_todos(data):
            if t['id'] == tid:
                for q, pq_label in PQ_LABEL.items():
                    if pq_label == label:
                        t['priority'] = q
                        break
                break
        save(data)
        self.refresh()

    def _remove_card(self, task_id):
        """Remove and destroy a task card widget."""
        card = self._task_cards.pop(task_id, None)
        if card and hasattr(card, 'destroy'):
            card.destroy()

    def _update_card(self, task_id, elapsed, total, done, paused):
        """Update card UI elements (time, progress, buttons) from timer state."""
        card = self._task_cards.get(task_id)
        if not card:
            return
        v = card.value
        v['time_lbl'].config(text='%02d:%02d / %02d:%02d' % (
            elapsed // 60, elapsed % 60, total // 60, total % 60))
        frac = elapsed / max(total, 1)
        v['prog'].config(value=frac * 100)
        try:
            remaining = total - elapsed
            if remaining > 60:
                v['prog'].config(style='Green.Horizontal')
            elif remaining > 10:
                v['prog'].config(style='Yellow.Horizontal')
            else:
                v['prog'].config(style='Red.Horizontal')
        except Exception:
            pass
        if not done:
            v['mins_cb'].state(['disabled'])
        else:
            v['mins_cb'].state(['readonly'])
        if done:
            v['start_btn'].config(text='Start', state='normal',
                                   command=lambda: self._panel_start_any(task_id))
            v['pause_btn'].config(text='Done', state='disabled')
        elif paused:
            v['start_btn'].config(text='Start', state='normal',
                                   command=lambda: self._panel_start_any(task_id))
            v['pause_btn'].config(text='Resume')
        else:
            v['start_btn'].config(text='Running', state='disabled')
            v['pause_btn'].config(text='Pause')

    def _todo_done(self, tid):
        data = load()
        for t in all_todos(data):
            if t['id'] == tid:
                t['done'] = True
                t['last_done'] = datetime.now().isoformat()
                break
        save(data)
        self.refresh()

    def _todo_remove(self, tid):
        if not messagebox.askyesno('Remove', 'Remove this task?'):
            return
        data = load()
        for project in data['projects']:
            for i, t in enumerate(project.get('todos', [])):
                if t['id'] == tid:
                    project['todos'].pop(i)
                    if tid in self.controller.timers:
                        self.controller.kill_timer(tid)
                    save(data)
                    self.refresh()
                    return

    def _panel_start_any(self, task_id):
        if task_id in self.controller.timers and not self.controller.timers[task_id]['runner'].done:
            return
        card = self._task_cards.get(task_id)
        if card:
            mins = int(card.value['mins_var'].get())
        else:
            mins = 25
        if self.controller.timer_for_task(task_id) is None:
            self.controller.start_timer_for(task_id, mins)
        self.refresh()
