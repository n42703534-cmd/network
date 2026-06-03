from pathlib import Path

src = Path("network.py").read_text(encoding="utf-8")
marker = Path("outputs/network_exec_progress.txt")
lines = src.splitlines()

instrumented = []
for idx, line in enumerate(lines, start=1):
    if idx in {1, 10, 14, 16, 1643, 1655, 1656, 1657, 1662, 1664, 1688, 1812, 2528, 4906, 5108}:
        instrumented.append(
            f"Path(r'outputs/network_exec_progress.txt').open('a', encoding='utf-8').write('before line {idx}\\n')"
        )
    instrumented.append(line)

code = "from pathlib import Path\n" + "\n".join(instrumented)
marker.write_text("start\n", encoding="utf-8")
ns = {"__name__": "network_exec_debug", "__file__": str(Path("network.py").resolve())}
exec(compile(code, "network.py", "exec"), ns)
marker.open("a", encoding="utf-8").write("done\n")
