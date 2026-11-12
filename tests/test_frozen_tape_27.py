"""Offline integrity tests for exact-feed preservation, not a trading backtest."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from research.frozen_tape_27 import _fingerprint, load_tape, save_tape


class FrozenTape27Tests(unittest.TestCase):
    def fixture(self):
        rows = [{"time": 1000, "open": 10.0, "high": 11.0,
                 "low": 9.0, "close": 10.5}]
        metadata = {"XAUUSD": {"sha256": _fingerprint(rows),
                                "bars": 1, "first": "1970-01-01",
                                "last": "1970-01-01"}}
        return rows, metadata

    def store(self, path, rows, meta):
        return save_tape(
            path, datasets={"XAUUSD": rows}, m15rows=None,
            price_data=meta, created_utc="2026-11-10T00:00:00Z",
            hist_start=1, hist_end=2000
        )

    def test_exact_feed_roundtrip(self):
        rows, meta = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tape.json.gz"
            self.store(path, rows, meta)
            restored = load_tape(path)
        self.assertEqual(restored["datasets"]["XAUUSD"], rows)
        self.assertEqual(restored["price_data"], meta)
        self.assertTrue(restored["paper_only"])

    def test_prices_changed_after_save_fail_hash_validation(self):
        rows, meta = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tape.json.gz"
            self.store(path, rows, meta)
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                obj = json.load(handle)
            obj["datasets"]["XAUUSD"][0]["close"] = 100.0
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                json.dump(obj, handle)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                load_tape(path)

    def test_source_and_metadata_disagreement_is_rejected(self):
        rows, meta = self.fixture()
        meta["XAUUSD"]["sha256"] = "invalid"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "provenance"):
                self.store(Path(folder) / "bad.json.gz", rows, meta)

    def test_no_empty_or_untracked_prices_can_be_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nope.json.gz"
            with self.assertRaises(ValueError):
                save_tape(path, datasets={}, m15rows=None, price_data={},
                          created_utc="now", hist_start=1, hist_end=2)

    def test_nonpaper_snapshot_is_rejected(self):
        rows, meta = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tape.json.gz"
            self.store(path, rows, meta)
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                obj = json.load(handle)
            obj["paper_only"] = False
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                json.dump(obj, handle)
            with self.assertRaisesRegex(ValueError, "schema"):
                load_tape(path)

    def test_invalid_window_is_rejected(self):
        rows, meta = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "window"):
                save_tape(Path(folder) / "bad.json.gz",
                          datasets={"XAUUSD": rows}, m15rows=None,
                          price_data=meta, created_utc="now",
                          hist_start=2000, hist_end=2000)


if __name__ == "__main__":
    unittest.main()
