# -*- coding: utf-8 -*-
# @Author: Bi Ying
# @Date:   2023-08-26 00:01:47
# @Last Modified by:   Bi Ying
# @Last Modified time: 2023-08-26 00:05:55
import subprocess
import os

# Get the current directory
current_dir = os.getcwd()

# Get the frontend directory
frontend_dir = os.path.join(current_dir, "..", "frontend")

# Start the frontend development
frontend_dev = subprocess.Popen(["pnpm", "run", "dev"], cwd=frontend_dir)

# Start the backend development
backend_dev = subprocess.Popen(["pdm", "run", "python", "main.py"], cwd=current_dir)

# Wait for both processes to complete
frontend_dev.wait()
backend_dev.wait()
