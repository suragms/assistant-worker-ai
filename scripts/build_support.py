"""Keep native dependency discovery independent of unrelated apps on PATH."""
import importlib.util
import os
from pathlib import Path
import sys


def isolate_native_search_path():
    if sys.platform != "win32":
        return
    windows = Path(os.environ["SystemRoot"])
    paths = [windows / "System32", windows, Path(sys.executable).parent, Path(sys.base_prefix)]
    qt = importlib.util.find_spec("PyQt6")
    if qt and qt.submodule_search_locations:
        paths.append(Path(next(iter(qt.submodule_search_locations))) / "Qt6" / "bin")
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(str(p) for p in paths if p.is_dir()))
