"""Short-lived file context. Never written to persistent assistant memory."""
from dataclasses import dataclass, field
from pathlib import Path
import time


@dataclass
class TaskMemory:
    folder: Path | None = None
    selected_file: Path | None = None
    file_type: str = ""
    touched: float = field(default_factory=time.monotonic)

    def clear(self):
        self.folder = self.selected_file = None
        self.file_type = ""
        self.touched = time.monotonic()

    def check(self):
        if time.monotonic() - self.touched > 600:
            self.clear()
        self.touched = time.monotonic()

    def newest(self, extension=".pdf"):
        self.check()
        if self.folder is None or not self.folder.is_dir():
            raise ValueError("Which folder should I search?")
        files = sorted((p for p in self.folder.iterdir() if p.is_file() and p.suffix.lower() == extension),
                       key=lambda p: p.stat().st_mtime_ns, reverse=True)
        if not files:
            raise ValueError(f"No {extension} files found in {self.folder.name}.")
        if len(files) > 1 and files[0].stat().st_mtime_ns == files[1].stat().st_mtime_ns:
            raise ValueError(f"Both {files[0].name} and {files[1].name} have the newest timestamp. Which one?")
        self.selected_file, self.file_type = files[0], extension
        return files[0]
