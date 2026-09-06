"""StatsTab — per-task pomodoro counts + total minutes from log."""
import os
from collections import defaultdict
import tkinter as tk
from tkinter import ttk
from pomodoro_common import LOG_FILE


class StatsTab(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build()

    def _build(self):
        inner = ttk.Frame(self)
        inner.pack(fill='both', expand=True, padx=12, pady=12)
        self.stats_tree = ttk.Treeview(inner, columns=('task', 'total_min', 'pomos', 'last_done'),
                                        show='headings', selectmode='browse')
        self.stats_tree.heading('task', text='Task')
        self.stats_tree.heading('total_min', text='Total min')
        self.stats_tree.heading('pomos', text='Pomos')
        self.stats_tree.heading('last_done', text='Last done')
        self.stats_tree.column('task', width=220, anchor='w')
        self.stats_tree.column('total_min', width=80, anchor='center')
        self.stats_tree.column('pomos', width=60, anchor='center')
        self.stats_tree.column('last_done', width=110, anchor='center')
        vsb = ttk.Scrollbar(inner, orient='vertical', command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=vsb.set)
        self.stats_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.stats_summary = ttk.Label(inner, text='Total: 0 pomodoros, 0 minutes this week',
                                        anchor='w', foreground='grey', font=('Consolas', 10))
        self.stats_summary.pack(fill='x', pady=(8, 0))
        self.refresh()

    def refresh(self):
        for row in self.stats_tree.get_children():
            self.stats_tree.delete(row)
        stats = self._load_stats()
        for task_id, s in stats.items():
            self.stats_tree.insert('', 'end', iid=task_id,
                                    values=(s['task'], s['total_min'], s['pomos'], s['last_done'][:16]))
        total_min = sum(s['total_min'] for s in stats.values())
        total_pomos = sum(s['pomos'] for s in stats.values())
        self.stats_summary.config(text='Total: %d pomodoros, %d minutes this week' % (total_pomos, total_min))

    def _load_stats(self):
        task_stats = defaultdict(lambda: {'task': '', 'total_min': 0, 'pomos': 0, 'last_done': ''})
        log = os.path.expanduser(LOG_FILE)
        if not os.path.exists(log):
            return dict(task_stats)
        with open(log, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 4 or parts[0] != 'DONE':
                    continue
                iso = parts[1]
                try:
                    mins = int(parts[2])
                except ValueError:
                    continue
                label = ' '.join(parts[3:]) if len(parts) > 3 else 'unknown'
                task_stats[label]['task'] = label
                task_stats[label]['total_min'] += mins
                task_stats[label]['pomos'] += 1
                if iso > task_stats[label]['last_done']:
                    task_stats[label]['last_done'] = iso
        return dict(task_stats)
