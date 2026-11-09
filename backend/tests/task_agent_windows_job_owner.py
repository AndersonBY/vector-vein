"""Disposable parent process for testing Windows job cleanup after abrupt host exit."""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from task_agent.windows_job import WindowsJob

root = Path(sys.argv[1])
child_code = (
    "import subprocess,sys,time;from pathlib import Path;"
    f"child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=subprocess.DETACHED_PROCESS);"
    f"Path({(root / 'grandchild.pid').as_posix()!r}).write_text(str(child.pid));time.sleep(60)"
)
with tempfile.TemporaryFile("w+b") as stdin, tempfile.TemporaryFile("w+b") as output:
    job = WindowsJob(
        [sys.executable, "-c", child_code],
        cwd=root,
        stdin_file=stdin,
        output_file=output,
        env=os.environ,
    )
    (root / "child.pid").write_text(str(job.pid))
    time.sleep(60)
