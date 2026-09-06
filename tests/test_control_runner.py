from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from ops.control_gateway.biella_control_runner import ProductionJournalTailer


class ProductionJournalTailerTest(unittest.TestCase):
    def test_replays_existing_events(self):
        with tempfile.TemporaryDirectory() as td:
            events = []
            journal = Path(td) / "events.jsonl"
            journal.write_text('{"seq":1,"lane":"Games","type":"task.started","text":"D03-01"}\n')
            tailer = ProductionJournalTailer(journal, lambda lane, event: events.append((lane, event)), poll_seconds=0.01)
            tailer.start()
            deadline = time.time() + 1
            while time.time() < deadline and not events:
                time.sleep(0.01)
            tailer.stop()
            self.assertTrue(any(lane == "Games" and event.get("text") == "D03-01" for lane, event in events))


if __name__ == "__main__":
    unittest.main()
