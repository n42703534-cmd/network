from pathlib import Path
import time

lines = Path("network.py").read_text(encoding="utf-8").splitlines()
for n in [1500, 1600, 1642, 1652, 1655, 1656, 1657, 1658, 1662, 1663, 1664, 1668]:
    code = "\n".join(lines[:n])
    t = time.time()
    ns = {"__name__": "x", "__file__": "network.py"}
    try:
        exec(compile(code, "network.py", "exec"), ns)
        print(n, "ok", round(time.time() - t, 2), flush=True)
    except Exception as exc:
        print(n, type(exc).__name__, str(exc)[:160], flush=True)
