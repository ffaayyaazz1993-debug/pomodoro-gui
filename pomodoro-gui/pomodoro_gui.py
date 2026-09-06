"""
pomodoro_gui.py — thin shell: creates controller + tabs, runs mainloop.
All tab logic lives in tabs/*.py, shared runtime in pomodoro_common.py,
shared state/timer engine in pomodoro_controller.py.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

from pomodoro_common import setup_styles, ChamferNotebook
from pomodoro_controller import PomodoroController
from tabs.todo_tab import TodoTab
from tabs.planner_tab import PlannerTab
from tabs.mindmap_tab import MindmapTab
from tabs.schedule_tab import ScheduleTab
from tabs.settings_tab import SettingsTab
from tabs.notes_tab import NotesTab
from tabs.stats_tab import StatsTab


def main():
    import sys as _sys
    if '--test' in _sys.argv:
        r = tk.Tk()
        r.withdraw()
        setup_styles(r)
        _run_test(r)
        return

    root = tk.Tk()
    root.title('Pomodoro Tool')
    root.geometry('820x580')
    root.minsize(720, 520)
    setup_styles(root)

    # shared state
    sound_on = tk.BooleanVar(value=True)
    auto_chain = tk.BooleanVar(value=False)
    dark_mode = tk.BooleanVar(value=False)
    project_var = tk.StringVar()

    # notebook
    nb = ChamferNotebook(root)
    nb.pack(fill='both', expand=True, padx=8, pady=8)

    # controller
    controller = PomodoroController(root, nb, sound_on, auto_chain, dark_mode, project_var)

    # tabs
    todo_tab = TodoTab(nb, controller)
    nb.add(todo_tab, text='Todo')

    planner_tab = PlannerTab(nb, controller)
    nb.add(planner_tab, text='Planner')

    mindmap_tab = MindmapTab(nb, controller)
    nb.add(mindmap_tab, text='Mindmap')

    schedule_tab = ScheduleTab(nb, controller)
    nb.add(schedule_tab, text='Schedule')

    settings_tab = SettingsTab(nb, controller)
    nb.add(settings_tab, text='Settings')

    notes_tab = NotesTab(nb, controller)
    nb.add(notes_tab, text='Notes')

    stats_tab = StatsTab(nb, controller)
    nb.add(stats_tab, text='Stats')

    # wire controller's placeholder methods to TodoTab's actual implementations
    controller._build_task_card = todo_tab._build_task_card
    controller._remove_card = todo_tab._remove_card
    controller._update_card = todo_tab._update_card

    # refresh tabs on timer events
    controller.on_timer_event(lambda: todo_tab.refresh())

    root.protocol('WM_DELETE_WINDOW', controller.on_close)
    try:
        root.update_idletasks()
        root.deiconify()
    except Exception:
        pass
    root.mainloop()


def _run_test(root):
    """Headless build check — verify all tabs construct without error."""
    from pomodoro_common import ChamferNotebook
    from pomodoro_controller import PomodoroController

    sound_on = tk.BooleanVar(value=True)
    auto_chain = tk.BooleanVar(value=False)
    dark_mode = tk.BooleanVar(value=False)
    project_var = tk.StringVar()

    nb = ChamferNotebook(root)
    controller = PomodoroController(root, nb, sound_on, auto_chain, dark_mode, project_var)

    todo_tab = TodoTab(nb, controller)
    nb.add(todo_tab, text='Todo')
    planner_tab = PlannerTab(nb, controller)
    nb.add(planner_tab, text='Planner')
    mindmap_tab = MindmapTab(nb, controller)
    nb.add(mindmap_tab, text='Mindmap')
    schedule_tab = ScheduleTab(nb, controller)
    nb.add(schedule_tab, text='Schedule')
    settings_tab = SettingsTab(nb, controller)
    nb.add(settings_tab, text='Settings')
    notes_tab = NotesTab(nb, controller)
    nb.add(notes_tab, text='Notes')
    stats_tab = StatsTab(nb, controller)
    nb.add(stats_tab, text='Stats')

    controller._build_task_card = todo_tab._build_task_card
    controller._remove_card = todo_tab._remove_card
    controller._update_card = todo_tab._update_card

    tabs = [nb.tab(i, 'text') for i in range(len(nb.tabs()))]
    root.destroy()
    print('GUI build OK — tabs:', tabs)


if __name__ == '__main__':
    main()
