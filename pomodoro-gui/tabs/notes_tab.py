"""NotesTab — per-task notes editor."""
import tkinter as tk
from tkinter import ttk
from pomodoro_common import load, save, all_todos


class NotesTab(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Notes for selected task:').pack(side='left')

        top2 = ttk.Frame(self)
        top2.pack(fill='both', expand=True, padx=8, pady=(0, 4))

        left = ttk.LabelFrame(top2, text='Tasks', padding=4)
        left.pack(side='left', fill='both', expand=True)
        self.notes_tree = ttk.Treeview(left, columns=('id', 'desc'), show='headings', selectmode='browse')
        self.notes_tree.heading('id', text='ID')
        self.notes_tree.heading('desc', text='Task')
        self.notes_tree.column('id', width=64, anchor='center')
        self.notes_tree.column('desc', width=180, anchor='w')
        vsb = ttk.Scrollbar(left, orient='vertical', command=self.notes_tree.yview)
        self.notes_tree.configure(yscrollcommand=vsb.set)
        self.notes_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.notes_tree.bind('<<TreeviewSelect>>', lambda e: self._select())

        right = ttk.LabelFrame(top2, text='Notes', padding=4)
        right.pack(side='right', fill='both', expand=True, padx=8)
        self.notes_text = tk.Text(right, wrap='word', width=50, height=16, font=('Consolas', 10))
        scr = ttk.Scrollbar(right, orient='vertical', command=self.notes_text.yview)
        self.notes_text.configure(yscrollcommand=scr.set)
        self.notes_text.pack(side='left', fill='both', expand=True)
        scr.pack(side='right', fill='y')
        self.notes_save_btn = ttk.Button(right, text='Save note', command=self._save)
        self.notes_save_btn.pack(anchor='e', padx=4, pady=4)

        self._refresh_list()

    def _refresh_list(self):
        for row in self.notes_tree.get_children():
            self.notes_tree.delete(row)
        data = load()
        for t in all_todos(data):
            if not t.get('done'):
                self.notes_tree.insert('', 'end', iid=t['id'], values=(t['id'], t['desc']))

    def _select(self):
        sel = self.notes_tree.selection()
        if not sel:
            self.notes_text.delete('1.0', 'end')
            return
        tid = sel[0]
        data = load()
        for t in all_todos(data):
            if t['id'] == tid:
                self.notes_text.delete('1.0', 'end')
                self.notes_text.insert('1.0', t.get('notes', '') or '')
                return

    def _save(self):
        sel = self.notes_tree.selection()
        if not sel:
            return
        tid = sel[0]
        text = self.notes_text.get('1.0', 'end-1c')
        data = load()
        for t in all_todos(data):
            if t['id'] == tid:
                t['notes'] = text
                break
        save(data)
        self.notes_save_btn.config(text='Saved', state='disabled')
        self.controller.master.after(1500, lambda: self.notes_save_btn.config(text='Save note', state='normal'))
