"""SettingsTab — sound, auto-chain, dark mode."""
import tkinter as tk
from tkinter import ttk
from pomodoro_common import DATA_FILE, LOG_FILE


class SettingsTab(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build()

    def _build(self):
        inner = ttk.Frame(self)
        inner.pack(expand=True, fill='both', padx=20, pady=20)
        ttk.Label(inner, text='Sound:').grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(inner, text='Enable sound on timer done', variable=self.controller.sound_on).grid(row=0, column=1, sticky='w')
        ttk.Separator(inner, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=12)
        ttk.Checkbutton(inner, text='Auto-start next task when timer finishes',
                        variable=self.controller.auto_chain).grid(row=1, column=1, sticky='w', padx=(20, 0))
        ttk.Separator(inner, orient='horizontal').grid(row=2, column=0, columnspan=2, sticky='ew', pady=12)
        ttk.Checkbutton(inner, text='Dark Mode', variable=self.controller.dark_mode,
                        command=self.controller.toggle_dark_mode).grid(row=3, column=0, sticky='w', columnspan=2)
        ttk.Button(inner, text='Close', command=self.controller.master.quit).grid(row=4, column=0, columnspan=2, pady=6)
        ttk.Label(inner, text='Data file: ' + DATA_FILE, foreground='grey').grid(row=5, column=0, columnspan=2, sticky='w')
        ttk.Label(inner, text='Log file: ' + LOG_FILE, foreground='grey').grid(row=6, column=0, columnspan=2, sticky='w')
