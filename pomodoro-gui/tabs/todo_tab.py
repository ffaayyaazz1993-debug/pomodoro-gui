"""TodoTab — Eisenhower-priority todo list with per-task timer cards."""
import os
import time
import uuid
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
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
        ttk.Button(top, text='+ Add', command=self._todo_add,
                    style='Primary.TButton').pack(side='left', padx=(4, 8))
        ttk.Label(top, text='Q:').pack(side='left', padx=(4, 0))
        self.todo_q = ttk.Combobox(top, values=[1, 2, 3, 4], width=3, state='readonly')
        self.todo_q.pack(side='left', padx=2)
        self.todo_q.set(2)
        ttk.Label(top, text='Cat:').pack(side='left', padx=(4, 0))
        self.todo_cat = ttk.Combobox(top, width=12)
        self.todo_cat.pack(side='left', padx=2)
        self.todo_cat.set('')
        self.todo_cat.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='+ Cat', style='Card.TButton',
                    command=self._add_category).pack(side='left', padx=2)
        ttk.Button(top, text='- Cat', style='Danger.TButton',
                    command=self._delete_category).pack(side='left', padx=2)
        ttk.Label(top, text='Tag:').pack(side='left', padx=(8, 0))
        self.todo_tag = ttk.Combobox(top, width=10)
        self.todo_tag.pack(side='left', padx=2)
        self.todo_tag.set('')
        self.todo_tag.bind('<<ComboboxSelected>>', self._on_tag_selected)
        self.todo_tag.bind('<KeyRelease>', lambda e: self._on_tag_selected(e))
        ttk.Button(top, text='Tags', style='Card.TButton',
                    command=self._open_tag_manager).pack(side='left', padx=2)

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

    def _on_tag_selected(self, event=None):
        """Tag selected — field inputs will render in the task card below the subtask bar."""
        pass

    def _todo_add(self):
        desc = self.todo_input_field.get().strip()
        if not desc:
            messagebox.showwarning('Add todo', 'Enter a task description.')
            return
        q = int(self.todo_q.get())
        cat = self.todo_cat.get().strip()
        tag = self.todo_tag.get().strip()
        data = load()
        project = get_current_project(data)
        todo = {'id': str(uuid.uuid4())[:8], 'desc': desc,
                'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'done': False, 'priority': q, 'pomodoros': 0,
                'last_done': '', 'notes': '', 'category': cat}
        if tag:
            todo['tag'] = tag
            # pre-fill tag_data with empty strings for each field defined on the tag
            tags_def = data.get('tags', {})
            if tag in tags_def and tags_def[tag]:
                todo['tag_data'] = {f['name']: '' for f in tags_def[tag]}
            else:
                todo['tag_data'] = {}
        project['todos'].append(todo)
        save(data)
        self.todo_input_field.delete(0, 'end')
        self.refresh()
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
        dialog.geometry('300x180')
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text='Folder name:').pack(padx=10, pady=(10, 4))
        name_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        entry.pack(padx=10); entry.focus()
        ttk.Label(dialog, text='Tag (optional):').pack(padx=10, pady=(8, 4))
        tag_var = tk.StringVar()
        data = load()
        tags = data.get('tags', {})
        tag_names = sorted(tags.keys())
        tag_combo = ttk.Combobox(dialog, textvariable=tag_var, values=tag_names, width=28)
        tag_combo.pack(padx=10)
        def do():
            name = name_var.get().strip()
            if name:
                data = load()
                cats = data.get('categories', [])
                cat_tags = data.get('category_tags', {})
                if name not in cats:
                    cats.append(name)
                    data['categories'] = sorted(cats)
                selected_tag = tag_var.get().strip()
                if selected_tag:
                    cat_tags[name] = selected_tag
                    data['category_tags'] = cat_tags
                save(data)
                self.todo_cat['values'] = [''] + data['categories']
                self.todo_cat.set(name)
                dialog.destroy()
        entry.bind('<Return>', lambda e: do())
        ttk.Button(dialog, text='Create', command=do).pack(pady=10)

    def _delete_category(self):
        cat = self.todo_cat.get().strip()
        if not cat:
            messagebox.showwarning('Delete Folder', 'Select a folder to delete.')
            return
        if not messagebox.askyesno('Delete Folder', 'Delete folder "%s"? Tasks in it will become uncategorized.' % cat):
            return
        data = load()
        cats = data.get('categories', [])
        if cat in cats:
            cats.remove(cat)
            data['categories'] = sorted(cats)
        # remove from category_tags
        cat_tags = data.get('category_tags', {})
        cat_tags.pop(cat, None)
        data['category_tags'] = cat_tags
        save(data)
        self.todo_cat['values'] = [''] + data['categories']
        self.todo_cat.set('')
        self.refresh()

    def _open_tag_manager(self):
        """Tag manager: define tags with custom fields. Category matching a tag name renders those fields."""
        dialog = tk.Toplevel(self)
        dialog.title('Tag Manager')
        dialog.geometry('420x350')
        dialog.transient(self)
        dialog.grab_set()

        # existing tags list
        list_frame = ttk.LabelFrame(dialog, text='Tags', padding=6)
        list_frame.pack(fill='both', expand=True, padx=10, pady=(10, 4))

        tag_listbox = tk.Listbox(list_frame, height=5)
        tag_listbox.pack(side='left', fill='both', expand=True)

        def refresh_tag_list():
            data = load()
            tags = data.get('tags', {})
            tag_listbox.delete(0, 'end')
            for name in sorted(tags.keys()):
                fields = tags[name]
                field_str = ', '.join(f['name'] for f in fields)
                tag_listbox.insert('end', '%s  [%s]' % (name, field_str))

        refresh_tag_list()

        # field editor
        field_frame = ttk.LabelFrame(dialog, text='Tag Editor', padding=6)
        field_frame.pack(fill='x', padx=10, pady=4)

        ttk.Label(field_frame, text='Tag name:').grid(row=0, column=0, sticky='w')
        tag_name_var = tk.StringVar()
        name_entry = ttk.Entry(field_frame, textvariable=tag_name_var, width=20)
        name_entry.grid(row=0, column=1, padx=4)

        ttk.Label(field_frame, text='Field name:').grid(row=1, column=0, sticky='w')
        field_name_var = tk.StringVar()
        field_name_entry = ttk.Entry(field_frame, textvariable=field_name_var, width=20)
        field_name_entry.grid(row=1, column=1, padx=4)

        ttk.Label(field_frame, text='Type:').grid(row=1, column=2, sticky='w')
        field_type_var = tk.StringVar(value='text')
        ttk.Combobox(field_frame, textvariable=field_type_var,
                     values=['text', 'number'], width=8,
                     state='readonly').grid(row=1, column=3, padx=4)

        def add_tag():
            tag = tag_name_var.get().strip()
            if not tag:
                return
            data = load()
            tags = data.setdefault('tags', {})
            if tag not in tags:
                tags[tag] = []
                data['tags'] = tags
                save(data)
            refresh_tag_list()

        ttk.Button(field_frame, text='+ Tag', command=add_tag).grid(row=0, column=2, padx=4)

        def add_field():
            tag = tag_name_var.get().strip()
            fname = field_name_var.get().strip()
            if not tag or not fname:
                return
            data = load()
            tags = data.setdefault('tags', {})
            if tag not in tags:
                tags[tag] = []
            tag_fields = tags[tag]
            if not any(f['name'] == fname for f in tag_fields):
                tag_fields.append({'name': fname, 'type': field_type_var.get()})
                tags[tag] = tag_fields
                save(data)
            field_name_var.set('')
            refresh_tag_list()

        ttk.Button(field_frame, text='+ Field', command=add_field).grid(row=1, column=4, padx=4)

        def delete_tag():
            sel = tag_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            data = load()
            tags = data.get('tags', {})
            # find tag name from display text
            display = tag_listbox.get(idx)
            tag_name = display.split('  [')[0].strip()
            if tag_name in tags:
                del tags[tag_name]
                data['tags'] = tags
                save(data)
            refresh_tag_list()

        btn_row = ttk.Frame(dialog)
        btn_row.pack(fill='x', padx=10, pady=4)
        ttk.Button(btn_row, text='Delete Tag', command=delete_tag).pack(side='left')
        ttk.Button(btn_row, text='Close', command=dialog.destroy).pack(side='right')

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

        data = load()
        persisted = set(data.get('categories', []))
        from_todos = set(t.get('category', '').strip() for t in todos if t.get('category', '').strip())
        cats_list = sorted(persisted | from_todos)
        self.todo_cat['values'] = [''] + cats_list

        tags_list = sorted(data.get('tags', {}).keys())
        self.todo_tag['values'] = [''] + tags_list

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
        cat = todo.get('category', '').strip() or 'No Category'
        tag = todo.get('tag', '').strip() or 'No Tag'
        ttk.Label(info, text='Cat: %s | Tag: %s' % (cat, tag),
                   foreground='#007aff', font=('SF Pro Text', 8)).pack(side='left', padx=(8, 4))
        ttk.Button(info, text='✎ Edit', style='Card.TButton',
                   command=lambda: self._edit_cat_tag(tid)).pack(side='left', padx=2)
        ttk.Button(info, text='✓', style='Accent.TButton',
                   command=lambda: self._todo_done(tid)).pack(side='right', padx=2)
        ttk.Button(info, text='✗', style='Danger.TButton',
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

        # time period row — start/end time + day + date
        self._build_time_period(card, tid, todo)

        subs = todo.get('subtasks', [])
        if subs:
            subs_frame = ttk.Frame(card)
            subs_frame.pack(fill='x', pady=(2, 0))
            for sub in subs:
                self._build_subtask_row(tid, sub, subs_frame)

        if self._detect_quran_related(todo):
            self._build_quran_meta(card, tid, todo)

        if self._detect_hadith_related(todo):
            self._build_hadith_meta(card, tid, todo)

        self._build_tag_fields(card, tid, todo)

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
        """Surah + Ayat side-by-side, then notes below — grouped as a Quran metadata section."""
        # surah + ayat in one row
        sa_frame = ttk.Frame(card)
        sa_frame.pack(fill='x', pady=(2, 0))
        ttk.Label(sa_frame, text='Surah:').pack(side='left', padx=(0, 4))
        surah_var = tk.StringVar(value=str(todo.get('surah', '')))
        surah_cb = ttk.Combobox(sa_frame, textvariable=surah_var,
                                 values=[str(i) for i in range(1, 115)],
                                 width=4, state='readonly')
        surah_cb.pack(side='left', padx=2)
        ttk.Label(sa_frame, text='Ayat:').pack(side='left', padx=(8, 4))
        ayat_var = tk.StringVar(value=str(todo.get('ayat', '')))
        ayat_cb = ttk.Combobox(sa_frame, textvariable=ayat_var,
                                values=[str(i) for i in range(1, self._surah_ayat_count(int(surah_var.get() or 1)) + 1)],
                                width=4, state='readonly')
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

        # notes box below
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

    def _detect_hadith_related(self, todo):
        cat = (todo.get('category') or '').strip().lower()
        if cat in ('hadith', 'hadith study', 'hadith review', 'sunnah'):
            return True
        text = (todo.get('desc') or '').lower()
        keywords = ('hadith', 'hadiths', 'sunnah', 'sahih', 'bukhari', 'muslim',
                    'tirmidhi', 'abudawud', 'nasai', 'ibnmajah', 'malik', 'muwatta',
                    'tirmizi', 'darimi', 'ahmad', 'shaikh', 'muhaddith', 'isnad',
                    'matn', 'sanad', 'kitab', 'bab', 'hadith no')
        return any(kw in text for kw in keywords)

    def _build_hadith_meta(self, card, tid, todo):
        """Hadith reference: book name, volume, kitab, hadith number."""
        frame = ttk.LabelFrame(card,
                                text='Hadith Reference',
                                padding=6,
                                style='Card.TLabelframe')
        frame.pack(fill='x', pady=(4, 0))

        # Row 1: Book Name
        row1 = ttk.Frame(frame)
        row1.pack(fill='x', pady=2)
        ttk.Label(row1, text='Book:', width=8).pack(side='left')
        book_var = tk.StringVar(value=str(todo.get('hadith_book', '') or ''))
        book_entry = ttk.Entry(row1, textvariable=book_var, width=30)
        book_entry.pack(side='left', padx=(0, 8))

        # Row 2: Volume, Kitab No, Hadith No
        row2 = ttk.Frame(frame)
        row2.pack(fill='x', pady=2)

        ttk.Label(row2, text='Vol:', width=4).pack(side='left')
        vol_var = tk.StringVar(value=str(todo.get('hadith_vol', '') or ''))
        vol_entry = ttk.Entry(row2, textvariable=vol_var, width=6)
        vol_entry.pack(side='left', padx=(0, 6))

        ttk.Label(row2, text='Kitab:', width=5).pack(side='left')
        kitab_var = tk.StringVar(value=str(todo.get('hadith_kitab', '') or ''))
        kitab_entry = ttk.Entry(row2, textvariable=kitab_var, width=20)
        kitab_entry.pack(side='left', padx=(0, 6))

        ttk.Label(row2, text='Hadith No:', width=8).pack(side='left')
        no_var = tk.StringVar(value=str(todo.get('hadith_no', '') or ''))
        no_entry = ttk.Entry(row2, textvariable=no_var, width=6)
        no_entry.pack(side='left')

        # Save on FocusOut / Return
        def save_field(*args):
            self._save_hadith_field(tid, {
                'hadith_book': book_var.get().strip(),
                'hadith_vol': vol_var.get().strip(),
                'hadith_kitab': kitab_var.get().strip(),
                'hadith_no': no_var.get().strip(),
            })

        for e in (book_entry, vol_entry, kitab_entry, no_entry):
            e.bind('<FocusOut>', save_field)
            e.bind('<Return>', save_field)

        card.value['hadith_book_var'] = book_var
        card.value['hadith_vol_var'] = vol_var
        card.value['hadith_kitab_var'] = kitab_var
        card.value['hadith_no_var'] = no_var

    def _save_hadith_field(self, tid, fields):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    for k, v in fields.items():
                        if v:
                            t[k] = v
                        elif k in t:
                            t.pop(k, None)
                    save(data)
                    return

    def _build_tag_fields(self, card, tid, todo):
        """Render tag field inputs below the subtask bar, inside the task card."""
        data = load()
        tags = data.get('tags', {})
        cat_tags = data.get('category_tags', {})
        cat = (todo.get('category') or '').strip()
        cat_lower = cat.lower()
        task_tag = (todo.get('tag') or '').strip()

        # find tag: task tag > category name match > category_tags map
        matched_tag = None
        if task_tag:
            for tag_name, fields in tags.items():
                if tag_name.lower() == task_tag.lower():
                    matched_tag = (tag_name, fields)
                    break
        if not matched_tag:
            for tag_name, fields in tags.items():
                if tag_name.lower() == cat_lower:
                    matched_tag = (tag_name, fields)
                    break
        if not matched_tag and cat in cat_tags:
            target_tag = cat_tags[cat]
            for tag_name, fields in tags.items():
                if tag_name.lower() == target_tag.lower():
                    matched_tag = (tag_name, fields)
                    break
        if not matched_tag:
            return

        tag_name, fields = matched_tag
        if not fields:
            return

        tag_data = todo.get('tag_data', {})

        for i, field in enumerate(fields):
            fname = field['name']
            row = ttk.Frame(card)
            row.pack(fill='x', pady=(2, 0))

            ttk.Label(row, text=fname + ':', width=9).pack(side='left')
            var = tk.StringVar(value=str(tag_data.get(fname, '') or ''))
            entry = ttk.Entry(row)
            entry.pack(side='left', fill='x', expand=True, padx=(2, 8))

            def save_field(*args, t=tid, fn=fname, v=var):
                self._save_tag_field(t, fn, v.get().strip())

            entry.bind('<FocusOut>', save_field)
            entry.bind('<Return>', save_field)

        card.value['tag_data'] = tag_data

    def _save_tag_field(self, tid, field_name, value):
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    tag_data = t.setdefault('tag_data', {})
                    if value:
                        tag_data[field_name] = value
                    else:
                        tag_data.pop(field_name, None)
                        if not tag_data:
                            t.pop('tag_data', None)
                    save(data)
                    return

    def _build_time_period(self, card, tid, todo):
        """Render start/end time + day + date row inside the task card."""
        import datetime as dt
        period = todo.get('time_period', {})

        row = ttk.Frame(card)
        row.pack(fill='x', pady=(2, 0))

        ttk.Label(row, text='Start:', font=('SF Pro Text', 8)).pack(side='left', padx=(0, 2))
        start_var = tk.StringVar(value=period.get('start', ''))
        start_entry = ttk.Entry(row, textvariable=start_var, width=6, font=('SF Pro Text', 8))
        start_entry.pack(side='left', padx=(0, 6))

        ttk.Label(row, text='End:', font=('SF Pro Text', 8)).pack(side='left', padx=(0, 2))
        end_var = tk.StringVar(value=period.get('end', ''))
        end_entry = ttk.Entry(row, textvariable=end_var, width=6, font=('SF Pro Text', 8))
        end_entry.pack(side='left', padx=(0, 6))

        ttk.Label(row, text='Day:', font=('SF Pro Text', 8)).pack(side='left', padx=(0, 2))
        day_var = tk.StringVar(value=period.get('day', ''))
        day_combo = ttk.Combobox(row, textvariable=day_var,
                                 values=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                                 width=5, state='readonly', font=('SF Pro Text', 8))
        day_combo.pack(side='left', padx=(0, 6))

        ttk.Label(row, text='Date:', font=('SF Pro Text', 8)).pack(side='left', padx=(0, 2))
        date_var = tk.StringVar(value=period.get('date', ''))
        date_entry = ttk.Entry(row, textvariable=date_var, width=11, font=('SF Pro Text', 8))
        date_entry.pack(side='left', padx=(0, 2))

        def save_period(*args):
            self._save_time_period(tid, {
                'start': start_var.get().strip(),
                'end': end_var.get().strip(),
                'day': day_var.get().strip(),
                'date': date_var.get().strip(),
            })

        start_entry.bind('<FocusOut>', save_period)
        start_entry.bind('<Return>', save_period)
        end_entry.bind('<FocusOut>', save_period)
        end_entry.bind('<Return>', save_period)
        day_combo.bind('<<ComboboxSelected>>', save_period)
        date_entry.bind('<FocusOut>', save_period)
        date_entry.bind('<Return>', save_period)

        # Auto-fill day from date when date changes
        def on_date_change(*args):
            d = date_var.get().strip()
            if len(d) == 10 and d[4] == '-' and d[7] == '-':
                try:
                    y, m, day_num = int(d[:4]), int(d[5:7]), int(d[8:10])
                    day_name = dt.date(y, m, day_num).strftime('%a')
                    day_var.set(day_name)
                except Exception:
                    pass
            save_period()

        date_entry.bind('<FocusOut>', on_date_change)
        date_entry.bind('<Return>', on_date_change)

    def _save_time_period(self, tid, period):
        """Save time_period dict to a task."""
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    # remove empty values
                    cleaned = {k: v for k, v in period.items() if v}
                    if cleaned:
                        t['time_period'] = cleaned
                    else:
                        t.pop('time_period', None)
                    save(data)
                    return

    def _detect_quran_related(self, todo):
        cat = (todo.get('category') or '').strip().lower()
        if cat == 'quran':
            return True
        text = (todo.get('desc') or '').lower()
        keywords = ('quran', 'surah', 'sura', 'ayat', 'ayah', 'falak', 'tauhid', 'tafseer',
                    'tafsir', 'hifz', 'huffaz', 'mufti', 'imam', 'mosque', 'masjid', 'dua',
                    'zakat', 'ramadan', 'roza', 'salah', 'namaz', 'wudu', 'kalima', 'allah',
                    'muhammad', 'islam', 'muslim')
        return any(kw in text for kw in keywords)

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


    def _edit_cat_tag(self, tid):
        """Edit Category / Tag / Time Period dialog for any task."""
        dialog = tk.Toplevel(self)
        dialog.title('Edit Task')
        dialog.geometry('320x400')
        dialog.transient(self)
        dialog.grab_set()

        todo = None
        data = load()
        for p in data['projects']:
            for t in p.get('todos', []):
                if t['id'] == tid:
                    todo = t
                    break
            if todo:
                break
        if not todo:
            return

        cur_cat = todo.get('category', '') or ''
        cur_tag = todo.get('tag', '') or ''
        period = todo.get('time_period', {})

        # Category
        ttk.Label(dialog, text='Category:').pack(padx=10, pady=(12, 2), anchor='w')
        cat_var = tk.StringVar(value=cur_cat)
        cat_frame = ttk.Frame(dialog)
        cat_frame.pack(fill='x', padx=10)
        cat_entry = ttk.Entry(cat_frame, textvariable=cat_var, width=30)
        cat_entry.pack(side='left', fill='x', expand=True)
        cat_btn = ttk.Button(cat_frame, text='+ Cat', style='Card.TButton',
                              command=lambda: self._quick_add_category(cat_var, cat_entry, cat_cb))
        cat_btn.pack(side='right', padx=(4, 0))
        all_cats = data.get('categories', [])
        cat_cb = ttk.Combobox(dialog, textvariable=cat_var, values=[''] + sorted(all_cats), width=30, state='readonly')
        cat_cb.pack(fill='x', padx=10)
        cat_cb.set(cur_cat)

        # Tag
        ttk.Label(dialog, text='Tag:').pack(padx=10, pady=(8, 2), anchor='w')
        tag_var = tk.StringVar(value=cur_tag)
        tag_frame = ttk.Frame(dialog)
        tag_frame.pack(fill='x', padx=10)
        tag_entry = ttk.Entry(tag_frame, textvariable=tag_var, width=30)
        tag_entry.pack(side='left', fill='x', expand=True)
        tag_btn = ttk.Button(tag_frame, text='TAGS', style='Card.TButton',
                              command=lambda: self._open_tag_manager())
        tag_btn.pack(side='right', padx=4)
        all_tags = sorted(data.get('tags', {}).keys())
        tag_cb = ttk.Combobox(dialog, textvariable=tag_var, width=30, state='readonly')
        tag_cb['values'] = [''] + all_tags
        tag_cb.pack(fill='x', padx=10)
        tag_cb.set(cur_tag)

        # Time Period
        ttk.Label(dialog, text='Time Period:').pack(padx=10, pady=(12, 2), anchor='w')
        period_frame = ttk.Frame(dialog)
        period_frame.pack(fill='x', padx=10)

        ttk.Label(period_frame, text='Start:').pack(side='left')
        start_var = tk.StringVar(value=period.get('start', ''))
        start_entry = ttk.Entry(period_frame, textvariable=start_var, width=6)
        start_entry.pack(side='left', padx=(2, 8))

        ttk.Label(period_frame, text='End:').pack(side='left')
        end_var = tk.StringVar(value=period.get('end', ''))
        end_entry = ttk.Entry(period_frame, textvariable=end_var, width=6)
        end_entry.pack(side='left', padx=(2, 8))

        day_frame = ttk.Frame(dialog)
        day_frame.pack(fill='x', padx=10, pady=(4, 0))
        ttk.Label(day_frame, text='Day:').pack(side='left')
        day_var = tk.StringVar(value=period.get('day', ''))
        day_combo = ttk.Combobox(day_frame, textvariable=day_var,
                                 values=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                                 width=5, state='readonly')
        day_combo.pack(side='left', padx=(2, 8))

        ttk.Label(day_frame, text='Date:').pack(side='left')
        date_var = tk.StringVar(value=period.get('date', ''))
        date_entry = ttk.Entry(day_frame, textvariable=date_var, width=11)
        date_entry.pack(side='left', padx=(2, 0))

        def do():
            cat = cat_var.get().strip()
            tag = tag_var.get().strip()
            todo['category'] = cat
            if tag:
                todo['tag'] = tag
            elif 'tag' in todo:
                del todo['tag']
            # save time period
            cleaned = {
                'start': start_var.get().strip(),
                'end': end_var.get().strip(),
                'day': day_var.get().strip(),
                'date': date_var.get().strip(),
            }
            cleaned = {k: v for k, v in cleaned.items() if v}
            if cleaned:
                todo['time_period'] = cleaned
            elif 'time_period' in todo:
                del todo['time_period']
            save(data)
            dialog.destroy()
            self.refresh()

        ttk.Button(dialog, text='Save', command=do).pack(pady=18)

    def _quick_add_category(self, var, entry, combo):
        """Prompt to create a new category without leaving the edit dialog."""
        name = simpledialog.askstring('New Category', 'Category name:')
        if name and name.strip():
            data = load()
            cats = data.get('categories', [])
            if name.strip() not in cats:
                cats.append(name.strip())
                data['categories'] = sorted(cats)
                save(data)
            var.set(name.strip())
            combo['values'] = [''] + sorted(cats)
            combo.set(name.strip())

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
