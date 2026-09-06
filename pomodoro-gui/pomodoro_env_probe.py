import os, sys
with open("C:/Users/ffaay/pomodoro_env_probe.txt","w") as f:
    f.write("HOME=%s\nUSERPROFILE=%s\nPATH=%s\nEXE=%s\nPY=%s\n" % (
        os.environ.get("HOME"),
        os.environ.get("USERPROFILE"),
        os.environ.get("PATH"),
        sys.executable,
        sys.version
    ))
