# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-08-26 00:01:47
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-07 16:37:17
import os
import sys
import signal
import subprocess


def kill_process_tree(pid, including_parent=True):
    try:
        if os.name == "nt":  # Windows
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(pid)])
        else:  # Unix-like system
            pids = subprocess.check_output(["pgrep", "-P", str(pid)]).split()
            for pid in pids:
                kill_process_tree(int(pid))
            if including_parent:
                os.kill(pid, signal.SIGKILL)
    except subprocess.CalledProcessError:
        pass


# Get the current directory
current_dir = os.getcwd()

# Get the frontend directory
frontend_dir = os.path.join(current_dir, "..", "frontend")

# Start the frontend development
frontend_dev = subprocess.Popen(["pnpm", "run", "dev"], cwd=frontend_dir)

# Start the backend development
backend_dev = subprocess.Popen(["pdm", "run", "python", "main.py"], cwd=current_dir)


def signal_handler(sig, frame):
    print("Exiting...")
    kill_process_tree(frontend_dev.pid)
    backend_dev.terminate()
    sys.exit(0)


# Capture SIGINT signal (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

# Wait for backend_dev process to complete
backend_dev.wait()

# If backend_dev exits, terminate frontend_dev and exit
kill_process_tree(frontend_dev.pid)
sys.exit(0)
