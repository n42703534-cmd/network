from pathlib import Path
import time

lines = Path("network.py").read_text(encoding="utf-8").splitlines()
for n in [17, 120, 180, 220, 400, 800, 1400, 1668, 1900, 2500, 3200, 4200, 4900, 5100]:
    code = "\n".join(lines[:n])
    t = time.time()
    ns = {"__name__": "x", "__file__": "network.py"}
    try:
        exec(compile(code, "network.py", "exec"), ns)
        print(n, "ok", round(time.time() - t, 2), flush=True)
    except Exception as exc:
        print(n, type(exc).__name__, str(exc)[:160], flush=True)
