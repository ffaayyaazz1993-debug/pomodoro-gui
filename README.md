# Pomodoro GUI

Tkinter-based pomodoro timer with per-tab split and controller architecture.

## Architecture

- **pomodoro_gui.py** — Thin shell: creates controller + tabs, runs mainloop
- **pomodoro_common.py** — Shared runtime: paths, Eisenhower constants, load/save, sound+toast, TimerRunner, ChamferNotebook, themes, mindmap geometry
- **pomodoro_controller.py** — Shared state + timer engine: tabs call controller instead of owning state
- **tabs/todo_tab.py** — Eisenhower todo list + per-task timer cards
- **tabs/mindmap_tab.py** — XMind-style canvas (nodes, edges, zoom, pan, drag)
- **tabs/planner_tab.py** — Weekly grid + task pool
- **tabs/schedule_tab.py** — schtasks-based recurring pomodoros
- **tabs/settings_tab.py** — Sound, auto-chain, dark mode
- **tabs/notes_tab.py** — Per-task notes editor
- **tabs/stats_tab.py** — Pomodoro counts + total minutes

Each tab is a ttk.Frame subclass that receives a PomodoroController reference. Controller owns the timer engine, task cards registry, project selection, and settings state. Timer events trigger todo_tab.refresh() via callback.

## Run

```bash
python pomodoro_gui.py
```

For a headless build check:

```bash
python pomodoro_gui.py --test
```
