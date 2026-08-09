import subprocess,sys
for cmd in ([sys.executable,"scripts/seed_agent_cases.py"],[sys.executable,"scripts/run_agent_eval.py"],[sys.executable,"-m","pytest","-q"]):
    if subprocess.run(cmd).returncode: raise SystemExit(1)
print("Stage 3 acceptance checks passed")
