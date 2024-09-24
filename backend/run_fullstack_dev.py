# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-08-26 00:01:47
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-07-11 12:05:05
import os
import re
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
frontend_proc = subprocess.Popen(
    ["pnpm", "run", "dev"], cwd=frontend_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)

# Capture the port number from the frontend process output
vite_port = None
vite_port_pattern = re.compile(r"VITE_PORT=(\d+)")

while True:
    if frontend_proc.stdout is None:
        break
    line = frontend_proc.stdout.readline()
    if line == "" and frontend_proc.poll() is not None:
        break
    match = vite_port_pattern.search(line)
    if match:
        vite_port = match.group(1)
        os.environ["VITE_LOCAL"] = f"http://localhost:{vite_port}/"
        break

if not vite_port:
    print("Failed to get Vite port.")
    sys.exit(1)

print(f"Vite is running on port {vite_port}")

# Start the backend development
backend_dev = subprocess.Popen(["pdm", "run", "python", "main.py"], cwd=current_dir)


def signal_handler(sig, frame):
    print("Exiting...")
    kill_process_tree(frontend_proc.pid)
    backend_dev.terminate()
    sys.exit(0)


# Capture SIGINT signal (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

# Wait for backend_dev process to complete
backend_dev.wait()

# If backend_dev exits, terminate frontend_proc and exit
kill_process_tree(frontend_proc.pid)
sys.exit(0)
