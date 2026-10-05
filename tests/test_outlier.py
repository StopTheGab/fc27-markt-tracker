"""Outlier filter: single glitch points are kept out of the series until confirmed."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector import db

T0 = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)


class OutlierTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = db.connect(Path(self.tmp.name) / "t.sqlite")
        for k in range(8):
            db.insert_price(self.con, "27-1", db.iso(T0 + timedelta(minutes=15 * k)), 167000 + k * 100, "live", "t")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def add(self, k, price):
        origin = db.classify_price(self.con, "27-1", price)
        db.insert_price(self.con, "27-1", db.iso(T0 + timedelta(minutes=15 * k)), price, origin, "t")
        return origin

    def test_glitch_is_suspect_and_excluded(self):
        self.assertEqual(self.add(8, 1500), "suspect")
        series = db.price_series(self.con, "27-1", db.iso(T0 - timedelta(days=1)))
        self.assertNotIn(1500, [p for _, p in series])
        self.assertEqual(self.add(9, 168000), "live")  # back to normal

    def test_confirmed_move_is_promoted(self):
        self.assertEqual(self.add(8, 60000), "suspect")
        self.assertEqual(self.add(9, 61000), "live")  # second point confirms a real crash
        series = [p for _, p in db.price_series(self.con, "27-1", db.iso(T0 - timedelta(days=1)))]
        self.assertIn(60000, series)
        self.assertIn(61000, series)

    def test_normal_move_is_live(self):
        self.assertEqual(self.add(8, 150000), "live")


if __name__ == "__main__":
    unittest.main()


class CreatorClassifyTest(unittest.TestCase):
    def test_kinds(self):
        from collector import creators
        self.assertEqual(creators.classify("FC 27: Jetzt in diese Spieler investieren", ""), "buy")
        self.assertEqual(creators.classify("FC 27: WANN TEAM KAUFEN / VERKAUFEN? Weekend League Marktanalyse", ""), "market")
        self.assertEqual(creators.classify("MARKET RISING BUT I MUST PLAY CHAMPS", ""), "market")
        self.assertEqual(creators.classify("SELL BEFORE THE CRASH", ""), "sell")
        self.assertEqual(creators.classify("She Is Going To Be EVERYWHERE", ""), "info")

    def test_name_match(self):
        from collector import creators
        cards = [{"id": "27-1", "name": "Kylian Mbappé"}, {"id": "27-2", "name": "Erling Haaland"}]
        pats = creators.name_patterns(cards)
        self.assertEqual(creators.match_cards("Mbappe und HAALAND jetzt kaufen", pats, {}), ["27-1", "27-2"])
        self.assertEqual(creators.match_cards("Mbappeee", pats, {}), [])
