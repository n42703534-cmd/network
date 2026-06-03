import sys
from pathlib import Path

log_path = Path("outputs/network_import_line_trace.txt")
log = log_path.open("w", encoding="utf-8")


def tracer(frame, event, arg):
    if event == "line" and frame.f_code.co_filename.endswith("network.py"):
        log.write(f"{frame.f_lineno}\n")
        log.flush()
    return tracer


sys.settrace(tracer)
import network  # noqa: E402,F401
sys.settrace(None)
log.write("DONE\n")
log.close()
