from pathlib import Path

marker = Path("outputs/import_debug_marker.txt")
marker.write_text("before network import\n", encoding="utf-8")
import network
marker.write_text("after network import\n", encoding="utf-8")
