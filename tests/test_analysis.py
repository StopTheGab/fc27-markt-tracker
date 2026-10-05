"""Logic tests with synthetic series in a temporary DB (never exported or published)."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector import analysis, db

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)  # Wednesday


def card(i, **kw):
    c = {"id": f"27-{1000 + i}", "name": f"Test {i}", "category": "trading",
         "_price_min": None, "_price_max": None, "_available": True}
    c.update(kw)
    return c


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = db.connect(Path(self.tmp.name) / "t.sqlite")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def fill(self, cid, days, price_fn, step_min=15, jitter=True):
        t = NOW - timedelta(days=days)
        while t <= NOW:
            noise = ((t.minute // 15) % 3) * 50 if jitter else 0  # liquid market: price moves a little
            db.insert_price(self.con, cid, db.iso(t), int(price_fn(t)) + noise, "live", "test")
            t += timedelta(minutes=step_min)
        self.con.commit()

    def flat_cards(self, n, days=5, price=10000):
        cards = [card(i) for i in range(n)]
        for c in cards:
            self.fill(c["id"], days, lambda t: price)
        return cards

    def test_metrics_gap_aware(self):
        # 5 days at 10k, then a 2-day gap: average must stay 10k, coverage < 1
        cid = "27-1"
        self.fill(cid, 7, lambda t: 10000 if t < NOW - timedelta(days=2) or t >= NOW - timedelta(hours=1) else None or 10000)
        s = db.price_series(self.con, cid, db.iso(NOW - timedelta(days=14)))
        m = analysis.card_metrics(s, NOW)
        self.assertAlmostEqual(m["avg_7d"], 10050, delta=30)

    def test_buy_signal_and_tax(self):
        cards = self.flat_cards(25)
        target = card(99)
        cards.append(target)
        self.fill(target["id"], 5, lambda t: 10000 if t < NOW - timedelta(minutes=40) else 8000)
        res = analysis.analyze(self.con, cards, NOW)
        sig = res["signals"].get(target["id"])
        self.assertIsNotNone(sig)
        self.assertEqual(sig["type"], "buy")
        self.assertEqual(sig["expected_profit"], round(sig["expected_sell"] * 0.95 - sig["price"]))
        self.assertLessEqual(sig["expected_sell"], sig["avg_7d"])
        self.assertGreater(sig["expected_profit"], 0)
        self.assertEqual(len(res["new_signals"]), 1)
        self.assertFalse(res["crash"]["active"])
        # second run: same signal is not new
        res2 = analysis.analyze(self.con, cards, NOW + timedelta(minutes=1))
        self.assertEqual(res2["new_signals"], [])

    def test_low_confidence_under_3_days(self):
        cards = self.flat_cards(25, days=1)
        target = card(99)
        cards.append(target)
        self.fill(target["id"], 1, lambda t: 10000 if t < NOW - timedelta(minutes=40) else 8000)
        res = analysis.analyze(self.con, cards, NOW)
        self.assertEqual(res["signals"][target["id"]]["confidence"], "gering")

    def test_no_signal_below_threshold(self):
        cards = self.flat_cards(25)
        target = card(99)
        cards.append(target)
        self.fill(target["id"], 5, lambda t: 10000 if t < NOW - timedelta(minutes=40) else 9000)
        res = analysis.analyze(self.con, cards, NOW)
        self.assertNotIn(target["id"], res["signals"])

    def test_price_floor_blocks_buy(self):
        cards = self.flat_cards(25)
        target = card(99, _price_min=8000)
        cards.append(target)
        self.fill(target["id"], 5, lambda t: 10000 if t < NOW - timedelta(minutes=40) else 8000)
        res = analysis.analyze(self.con, cards, NOW)
        self.assertNotIn(target["id"], res["signals"])

    def test_untradeable_blocks_buy(self):
        cards = self.flat_cards(25)
        target = card(99, _available=False)
        cards.append(target)
        self.fill(target["id"], 5, lambda t: 10000 if t < NOW - timedelta(minutes=40) else 8000)
        res = analysis.analyze(self.con, cards, NOW)
        self.assertNotIn(target["id"], res["signals"])

    def test_market_crash_suppresses_buys(self):
        cards = [card(i) for i in range(30)]
        for c in cards:
            self.fill(c["id"], 5, lambda t: 10000 if t < NOW - timedelta(hours=20) else 8000)
        res = analysis.analyze(self.con, cards, NOW)
        self.assertTrue(res["crash"]["active"])
        self.assertEqual([s for s in res["signals"].values() if s["type"] == "buy"], [])
        self.assertTrue(res["crash_new"])

    def test_sell_after_buy_and_rearm(self):
        cards = self.flat_cards(25)
        target = card(99)
        cards.append(target)
        self.fill(target["id"], 5, lambda t: 10000 if t < NOW - timedelta(minutes=40) else 8000)
        analysis.analyze(self.con, cards, NOW)
        # price recovers above the average one hour later
        later = NOW + timedelta(hours=1)
        for k in range(1, 5):
            db.insert_price(self.con, target["id"], db.iso(NOW + timedelta(minutes=15 * k)), 10500, "live", "test")
        for c in cards[:-1]:
            for k in range(1, 5):
                db.insert_price(self.con, c["id"], db.iso(NOW + timedelta(minutes=15 * k)), 10000, "live", "test")
        self.con.commit()
        res = analysis.analyze(self.con, cards, later)
        sig = res["signals"].get(target["id"])
        self.assertIsNotNone(sig)
        self.assertEqual(sig["type"], "sell")
        self.assertIn(target["id"], [s["card_id"] for s in res["new_signals"]])
        hr = analysis.hit_rate(self.con, later)
        self.assertEqual(hr["hits"], 1)

    def test_rearm_within_2h_not_new(self):
        r = analysis.rules()
        sig = {"card_id": "27-5", "type": "buy"}
        self.assertEqual(len(analysis.update_signal_state(self.con, {"27-5": dict(sig)}, NOW, r)), 1)
        analysis.update_signal_state(self.con, {}, NOW + timedelta(minutes=15), r)  # vanished
        again = analysis.update_signal_state(self.con, {"27-5": dict(sig)}, NOW + timedelta(minutes=60), r)
        self.assertEqual(again, [])  # within 2 h -> not new
        analysis.update_signal_state(self.con, {}, NOW + timedelta(minutes=75), r)
        again2 = analysis.update_signal_state(self.con, {"27-5": dict(sig)}, NOW + timedelta(hours=4), r)
        self.assertEqual(len(again2), 1)


    def test_flat_price_blocks_buy(self):
        cards = self.flat_cards(25)
        target = card(99)
        cards.append(target)
        self.fill(target["id"], 5, lambda t: 10000 if t < NOW - timedelta(minutes=40) else 8000, jitter=False)
        # only one change in 24 h -> illiquid / frozen quote
        res = analysis.analyze(self.con, cards, NOW)
        self.assertNotIn(target["id"], res["signals"])


if __name__ == "__main__":
    unittest.main()
