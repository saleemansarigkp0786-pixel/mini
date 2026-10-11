"""Load the fictional DegreePath DEMO DATA curriculum through Flask's CLI."""
import subprocess
import sys


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "flask", "--app", "run.py", "load-demo-data"]))
