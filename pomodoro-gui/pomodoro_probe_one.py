import os, sys, time
sys.path.insert(0, "C:/Users/ffaay")
import pomodoro_tool
pomodoro_tool.run_only(1, "Probe test")
# marker
with open("C:/Users/ffaay/pomodoro_probe_done.txt","w") as f:
    f.write("probe done\n")
