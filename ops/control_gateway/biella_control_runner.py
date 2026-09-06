from __future__ import annotations

import json
import threading
from pathlib import Path


class ProductionJournalTailer:
    def __init__(self, path: Path, publish, *, poll_seconds: float = 0.2, replay_bytes: int = 262144):
        self.path = Path(path)
        self.publish = publish
        self.poll_seconds = poll_seconds
        self.replay_bytes = replay_bytes
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="biella-production-journal", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        position: int | None = None
        while not self._stop.is_set():
            if not self.path.exists():
                self._stop.wait(self.poll_seconds)
                continue
            try:
                size = self.path.stat().st_size
                if position is not None and size < position:
                    position = 0
                if position is None:
                    position = max(0, size - self.replay_bytes)
                    with self.path.open("rb") as handle:
                        handle.seek(position)
                        if position:
                            handle.readline()
                            position = handle.tell()
                with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(position)
                    while not self._stop.is_set():
                        line = handle.readline()
                        if not line:
                            position = handle.tell()
                            break
                        position = handle.tell()
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(event, dict):
                            self.publish("Games", event)
            except OSError:
                position = None
            self._stop.wait(self.poll_seconds)

