"""Pruef-Agent 2026-10-05: Vertrags-, Krypto-, Luecken-, Mail- und Signal-Neu-Tests.

Nur synthetische Daten in temporaeren DBs/Ordnern. Nichts wird exportiert, gepusht oder gemailt.
Bekannte Abweichungen von den Vorgaben sind als expectedFailure markiert (Suite bleibt gruen,
die Abweichung bleibt sichtbar).
"""
import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from collector import analysis, crypto, db, export, mailer
from collector.config import Settings

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)  # Mittwoch, 14:00 MESZ
ISO_Z = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def card(i, **kw):
    c = {"id": f"27-{1000 + i}", "name": f"Test {i}", "category": "trading", "version": "Gold Rare",
         "rating": 85, "position": "ST", "_price_min": None, "_price_max": None, "_available": True}
    c.update(kw)
    return c


def no_mail_settings(**extra):
    env = {"MAIL_PROVIDER": "none", "DATA_PUBLISH_ENABLED": "false", "DATA_KEY": crypto.b64url(os.urandom(32))}
    env.update(extra)
    return Settings(env)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.con = db.connect(self.dir / "t.sqlite")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def fill(self, cid, days, price_fn, end=NOW, step_min=15):
        t = end - timedelta(days=days)
        while t <= end:
            noise = ((t.minute // 15) % 3) * 50
            db.insert_price(self.con, cid, db.iso(t), int(price_fn(t)) + noise, "live", "test")
            t += timedelta(minutes=step_min)
        self.con.commit()

    def market_with_target(self, target_price=8000, days=5):
        cards = [card(i) for i in range(25)]
        for c in cards:
            self.fill(c["id"], days, lambda t: 10000)
        target = card(99)
        cards.append(target)
        self.fill(target["id"], days, lambda t: 10000 if t < NOW - timedelta(minutes=40) else target_price)
        return cards, target


# ---------------------------------------------------------------- export vs DATA_CONTRACT
class ExportContractTest(Base):
    CARD_KEYS = {"id", "ea_id", "name", "version", "rating", "position", "league", "club", "nation", "price",
                 "price_updated_at", "available", "price_min", "price_max", "avg_7d", "change_1h_pct",
                 "change_24h_pct", "deviation_pct", "data_days", "signal", "watch_reason", "image", "link"}
    STATUS_KEYS = {"generated_at", "last_successful_fetch", "source", "collector_version", "interval_minutes",
                   "cards_tracked", "cards_with_price", "data_days", "gaps", "errors_last_run"}
    MARKET_KEYS = {"generated_at", "trend_24h_pct", "trend_1h_pct", "index_value", "crash", "week_phase",
                   "upcoming_events", "assessment", "hit_rate"}
    SIGNAL_KEYS = {"card_id", "name", "type", "since", "price", "avg_7d", "deviation_pct", "expected_sell",
                   "expected_profit", "confidence", "reasons", "rules"}

    def run_export(self):
        cards, target = self.market_with_target()
        self.con.execute("INSERT INTO runs(started_at,finished_at,ok,prices) VALUES(?,?,1,26)",
                         (db.iso(NOW - timedelta(minutes=15)), db.iso(NOW - timedelta(minutes=9))))
        self.con.commit()
        res = analysis.analyze(self.con, cards, NOW)
        out = self.dir / "export"
        with mock.patch.object(export, "EXPORT_DIR", out), mock.patch.object(db, "utcnow", return_value=NOW):
            export.export_all(self.con, cards, res, {"id": "test", "name": "T", "url": "", "ok": True, "message": "ok"}, [])
        return out, target

    def load(self, out, name):
        return json.loads((out / name).read_text(encoding="utf-8"))

    def test_status_market_cards_signals_history(self):
        out, target = self.run_export()
        st = self.load(out, "status.json")
        self.assertTrue(self.STATUS_KEYS <= st.keys(), self.STATUS_KEYS - st.keys())
        self.assertRegex(st["generated_at"], ISO_Z)
        mk = self.load(out, "market.json")
        self.assertTrue(self.MARKET_KEYS <= mk.keys(), self.MARKET_KEYS - mk.keys())
        self.assertIn(mk["crash"]["severity"], ("none", "mild", "severe"))
        self.assertIn(mk["assessment"]["author"], ("Regeln", "Analyse-Runde"))
        cs = self.load(out, "cards.json")
        self.assertEqual(len(cs["cards"]), 26)
        self.assertEqual(len({c["id"] for c in cs["cards"]}), 26)
        for c in cs["cards"]:
            self.assertTrue(self.CARD_KEYS <= c.keys(), self.CARD_KEYS - c.keys())
            self.assertIsInstance(c["price"], int)
            self.assertGreater(c["price"], 0)
            self.assertIsInstance(c["avg_7d"], int)
            self.assertRegex(c["price_updated_at"], ISO_Z)
            self.assertIn(c["signal"], ("buy", "sell", None))
            self.assertAlmostEqual(c["deviation_pct"], (c["price"] - c["avg_7d"]) / c["avg_7d"] * 100, places=1)
        sg = self.load(out, "signals.json")
        self.assertEqual([s["card_id"] for s in sg["signals"]], [target["id"]])
        s = sg["signals"][0]
        self.assertTrue(self.SIGNAL_KEYS <= s.keys(), self.SIGNAL_KEYS - s.keys())
        self.assertEqual(s["expected_profit"], round(s["expected_sell"] * 0.95 - s["price"]))
        self.assertGreater(s["expected_profit"], 0)
        self.assertIn(s["confidence"], ("hoch", "mittel", "gering"))
        self.assertRegex(s["since"], ISO_Z)
        h = self.load(out, f"history/{target['id']}.json")
        self.assertEqual(h["card_id"], target["id"])
        for ts, p in h["points"]:
            self.assertRegex(ts, ISO_Z)
            self.assertIsInstance(p, int)
            self.assertGreaterEqual(db.parse(ts), NOW - timedelta(days=14))

    def test_compress_history_hourly_after_48h(self):
        series = [(NOW - timedelta(hours=72) + timedelta(minutes=15 * k), 1000 + k) for k in range(4 * 72 + 1)]
        pts = export.compress_history(series, NOW)
        old = [p for p in pts if db.parse(p[0]) < NOW - timedelta(hours=48)]
        self.assertEqual(len(old), 24)  # 24 hourly buckets
        self.assertTrue(all(db.parse(t).minute == 0 for t, _ in old))
        self.assertEqual(len(pts) - len(old), 4 * 48 + 1)

    def test_last_successful_fetch_includes_current_run(self):
        """B6 (behoben): run_once uebergibt den laufenden Lauf als current_ok an export_all."""
        prev = NOW - timedelta(hours=3)
        self.con.execute("INSERT INTO runs(started_at,ok,prices) VALUES(?,1,10)", (db.iso(prev),))
        self.con.execute("INSERT INTO runs(started_at,ok) VALUES(?,0)", (db.iso(NOW),))  # laufender Lauf
        self.con.commit()
        out = self.dir / "export"
        with mock.patch.object(export, "EXPORT_DIR", out), mock.patch.object(db, "utcnow", return_value=NOW + timedelta(minutes=6)):
            export.export_all(self.con, [], None, {"ok": True}, [], current_ok=db.iso(NOW))
        st = json.loads((out / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(st["last_successful_fetch"], db.iso(NOW))
        self.assertTrue(all(g["to"] is not None for g in st["gaps"]))  # no false open gap


# ---------------------------------------------------------------- gaps
class GapsTest(Base):
    def add_run(self, t, ok=1):
        self.con.execute("INSERT INTO runs(started_at,ok) VALUES(?,?)", (db.iso(t), ok))

    def test_gaps(self):
        t0 = NOW - timedelta(hours=6)
        for k in range(4):                       # 4 Laeufe, 15 min Abstand
            self.add_run(t0 + timedelta(minutes=15 * k))
        self.add_run(t0 + timedelta(minutes=60), ok=0)    # fehlgeschlagen: zaehlt nicht
        self.add_run(t0 + timedelta(minutes=165))         # Luecke 120 min (von +45 bis +165)
        self.add_run(t0 + timedelta(minutes=180))
        self.con.commit()
        g = export.gaps(self.con, NOW)
        self.assertEqual(g[0], {"from": db.iso(t0 + timedelta(minutes=45)), "to": db.iso(t0 + timedelta(minutes=165)),
                                "minutes": 120})
        self.assertEqual(g[-1]["to"], None)              # offene Luecke bis jetzt (180 min)
        self.assertEqual(g[-1]["minutes"], 180)
        self.assertEqual(len(g), 2)

    def test_no_gap_for_regular_runs(self):
        for k in range(8):
            self.add_run(NOW - timedelta(minutes=15 * k))
        self.con.commit()
        self.assertEqual(export.gaps(self.con, NOW + timedelta(minutes=5)), [])


# ---------------------------------------------------------------- crypto
class CryptoTest(unittest.TestCase):
    def test_roundtrip_and_envelope(self):
        key = crypto.b64url(os.urandom(32))
        plain = json.dumps({"x": "Mbappé", "p": 3739000}, ensure_ascii=False).encode()
        env = json.loads(crypto.encrypt_file_json(key, plain))
        self.assertEqual(env["alg"], "AES-256-GCM")
        self.assertEqual(set(env), {"v", "alg", "iv", "ct"})
        self.assertEqual(crypto.decrypt_envelope(key, env), plain)
        self.assertNotIn(b"3739000", env["ct"].encode())
        env2 = json.loads(crypto.encrypt_file_json(key, plain))
        self.assertNotEqual(env["iv"], env2["iv"])  # frische IV pro Datei

    def test_wrong_key_and_tamper_fail(self):
        key, other = crypto.b64url(os.urandom(32)), crypto.b64url(os.urandom(32))
        env = crypto.encrypt_bytes(key, b"{}")
        with self.assertRaises(Exception):
            crypto.decrypt_envelope(other, env)
        bad = dict(env, ct=env["ct"][:-4] + ("AAAA" if not env["ct"].endswith("AAAA") else "BBBB"))
        with self.assertRaises(Exception):
            crypto.decrypt_envelope(key, bad)

    def test_ensure_key_uses_existing(self):
        with mock.patch("builtins.open", side_effect=AssertionError("darf .env nicht schreiben")):
            self.assertEqual(crypto.ensure_key({"DATA_KEY": "abc"}), "abc")


# ---------------------------------------------------------------- mail texts (MAIL_PROVIDER=none)
class MailTest(Base):
    def setUp(self):
        super().setUp()
        self.sent = []
        self.patch_net = mock.patch.object(mailer.requests, "post", side_effect=AssertionError("kein Netz!"))
        self.patch_net.start()

    def tearDown(self):
        self.patch_net.stop()
        super().tearDown()

    def capture(self, con, settings, kind, subject, text, html_body):
        self.sent.append((kind, subject, text, html_body))
        return False  # wie MAIL_PROVIDER=none

    def test_provider_none_sends_nothing(self):
        s = no_mail_settings()
        self.assertFalse(mailer.send(self.con, s, "signal", "[FC27 SIGNAL] x", "t", "<p>t</p>"))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM mail_log").fetchone()[0], 0)
        self.assertEqual(mailer._send(s, "a", "b", "c")[0], False)

    def test_signal_mail_single_and_bundle(self):
        cards, target = self.market_with_target()
        res = analysis.analyze(self.con, cards, NOW)
        s = no_mail_settings()
        with mock.patch.object(mailer, "send", side_effect=self.capture):
            mailer.signal_mail(self.con, s, res)
            kind, subject, text, html_body = self.sent[-1]
            self.assertEqual(kind, "signal")
            self.assertRegex(subject, r"^\[FC27 SIGNAL\] Kauf: Test 99 -\d+ %$")
            self.assertIn("KAUFEN: Test 99", text)
            self.assertIn("Erwarteter Gewinn nach Steuer", text)
            self.assertIn("Zum Dashboard", html_body)
            # zwei neue Signale -> eine gesammelte Mail
            two = dict(res, new_signals=[res["new_signals"][0], dict(res["new_signals"][0], card_id="27-2", name="B")])
            mailer.signal_mail(self.con, s, two)
            self.assertEqual(self.sent[-1][1], "[FC27 SIGNAL] 2 Kauf / 0 Verkauf")
            self.assertEqual(self.sent[-1][2].count("KAUFEN:"), 2)
            n = len(self.sent)
            mailer.signal_mail(self.con, s, dict(res, new_signals=[], crash_new=False))
            self.assertEqual(len(self.sent), n)  # nichts Neues -> keine Mail

    def test_crash_mail_subject(self):
        res = {"new_signals": [], "crash_new": True, "crash": {"drop_pct": -12.0, "reason": "Median -12 %"},
               "suppressed_by_crash": 9}
        with mock.patch.object(mailer, "send", side_effect=self.capture):
            mailer.signal_mail(self.con, no_mail_settings(), res)
        self.assertTrue(self.sent[-1][1].startswith("[FC27 SIGNAL] Marktcrash"))
        self.assertIn("9 Einzel-Kaufsignale", self.sent[-1][2])

    def test_hourly_subject_once_per_hour(self):
        cards, _ = self.market_with_target()
        res = analysis.analyze(self.con, cards, NOW)
        s = no_mail_settings()
        with mock.patch.object(mailer, "send", side_effect=self.capture):
            mailer.hourly_mail(self.con, s, res, cards)
            self.assertEqual(self.sent[-1][1], "[FC27 Update] 14:00")  # 12:00 UTC = 14:00 MESZ
            self.assertIn("Offene Signale:", self.sent[-1][2])
            mailer.hourly_mail(self.con, s, dict(res, now=NOW + timedelta(minutes=15)), cards)
            self.assertEqual(len(self.sent), 1)  # gleiche Stunde -> keine zweite Mail
            mailer.hourly_mail(self.con, s, dict(res, now=NOW + timedelta(minutes=60)), cards)
            self.assertEqual(self.sent[-1][1], "[FC27 Update] 15:00")


# ---------------------------------------------------------------- signal rules
def metrics(price, avg=10000, days=5.0, **kw):
    m = {"price": price, "avg_7d": avg, "data_hours": days * 24, "data_days": days, "coverage": 1.0,
         "recent": [price, price], "changes_24h": 20, "cv": 0.05, "trend_72h_pct": None, "avg_72h": None,
         "stale": False}
    m.update(kw)
    return m


LATE = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)  # nach release_phase_end


class SignalRuleTest(Base):
    def setUp(self):
        super().setUp()
        self.r = analysis.rules()

    def test_dynamic_limit_and_strong_signal(self):
        """Seit 2026-10-05: Kauflimit = Schnitt - max(8 %, 2 x Schwankung); >= 15 % = starkes Signal."""
        m = metrics(8510)
        lim = analysis.card_limits(m, self.r)
        self.assertGreaterEqual(lim["threshold_pct"], 8.0)
        self.assertLessEqual(lim["threshold_pct"], 20.0)
        sig = analysis.evaluate_buy(card(1), m, LATE, {}, self.r)
        self.assertEqual(sig["strength"], "normal")
        self.assertEqual(analysis.evaluate_buy(card(1), metrics(8500), LATE, {}, self.r)["strength"], "stark")
        self.assertIsNone(analysis.evaluate_buy(card(1), metrics(9300), LATE, {}, self.r))  # only -7 %: below tax floor
        self.assertEqual(analysis.price_step(23400), 250)
        self.assertEqual(analysis.round_down(23400), 23250)
        self.assertEqual(analysis.round_up(23400), 23500)

    def test_profit_formula_and_confidence(self):
        sig = analysis.evaluate_buy(card(1), metrics(8000), LATE, {}, self.r)
        self.assertEqual(sig["expected_profit"], round(10000 * 0.95 - 8000))
        self.assertEqual(sig["confidence"], "hoch")
        low = analysis.evaluate_buy(card(1), metrics(8000, days=2.9), LATE, {}, self.r)
        self.assertEqual(low["confidence"], "gering")

    def test_unavailable_floor_and_min_price(self):
        self.assertIsNone(analysis.evaluate_buy(card(1, _available=False), metrics(8000), LATE, {}, self.r))
        self.assertIsNone(analysis.evaluate_buy(card(1, _price_min=7800), metrics(8000), LATE, {}, self.r))
        self.assertIsNone(analysis.evaluate_buy(card(1), metrics(650, avg=900), LATE, {}, self.r))
        self.assertIsNone(analysis.evaluate_buy(card(1), metrics(8000, stale=True), LATE, {}, self.r))

    def test_new_only_if_previous_run_had_none(self):
        sig = {"card_id": "27-5", "type": "buy"}
        r = self.r
        self.assertEqual(len(analysis.update_signal_state(self.con, {"27-5": dict(sig)}, NOW, r)), 1)
        self.assertEqual(analysis.update_signal_state(self.con, {"27-5": dict(sig)}, NOW + timedelta(minutes=15), r), [])
        # Typwechsel buy -> sell gilt als neu
        sell = analysis.update_signal_state(self.con, {"27-5": {"card_id": "27-5", "type": "sell"}},
                                            NOW + timedelta(minutes=30), r)
        self.assertEqual(len(sell), 1)

    def test_rearm_boundary_exactly_2h(self):
        sig = {"card_id": "27-6", "type": "buy"}
        analysis.update_signal_state(self.con, {"27-6": dict(sig)}, NOW, self.r)
        analysis.update_signal_state(self.con, {}, NOW + timedelta(minutes=15), self.r)
        again = analysis.update_signal_state(self.con, {"27-6": dict(sig)}, NOW + timedelta(minutes=135), self.r)
        self.assertEqual(len(again), 1)  # genau 2 h nach dem Verschwinden -> wieder neu

    def test_crash_suppresses_but_mails_crash_once(self):
        cards = [card(i) for i in range(30)]
        for c in cards:
            self.fill(c["id"], 5, lambda t: 10000 if t < NOW - timedelta(hours=20) else 8000)
        res = analysis.analyze(self.con, cards, NOW)
        self.assertTrue(res["crash"]["active"] and res["crash_new"])
        self.assertEqual(res["new_signals"], [])
        res2 = analysis.analyze(self.con, cards, NOW + timedelta(minutes=1))
        self.assertFalse(res2["crash_new"])

    def test_sell_signal_only_with_positive_profit(self):
        """ABWEICHUNG: Verkaufssignal kommt bei Preis >= Schnitt auch, wenn Verkauf*0,95 - Kauf < 0
        (7-Tage-Schnitt ist seit dem Kauf gefallen). Vorgabe: Gewinn nur positiv."""
        cards = [card(i) for i in range(25)]
        for c in cards:
            self.fill(c["id"], 5, lambda t: 10000)
        target = card(99)
        cards.append(target)
        self.fill(target["id"], 5, lambda t: 9300 if t < NOW - timedelta(minutes=10) else 9400)
        self.con.execute("INSERT INTO tips(card_id,created_at,buy_price,avg_7d,expected_profit) VALUES(?,?,?,?,?)",
                         (target["id"], db.iso(NOW - timedelta(days=1)), 9000, 10800, 1260))
        self.con.commit()
        res = analysis.analyze(self.con, cards, NOW)
        sig = res["signals"].get(target["id"])
        self.assertTrue(sig is None or sig["expected_profit"] > 0, sig and sig["expected_profit"])


# ---------------------------------------------------------------- FUTNext cache vs. 15-min interval
class FutNextCacheTest(unittest.TestCase):
    def test_card_fetched_late_in_previous_run_is_refetched(self):
        """BUG: FUTNEXT_MIN_REFETCH_MIN=14 wird gegen den START des Laufs gemessen. Eine Karte, die im
        vorigen Lauf erst nach >1 min abgerufen wurde, gilt beim naechsten Lauf (15 min) noch als frisch:
        der Cache-Wert mit altem fetched_at wird erneut geliefert, INSERT OR IGNORE verwirft ihn.
        Real: ~120 von 146 Karten nur alle 30 min neu (DB: :15/:45-Laeufe ~22 neue Punkte)."""
        from collector.sources import futnext
        src = futnext.FutNextSource({"FUTNEXT_DISK_CACHE": "0"})
        run_start = datetime(2026, 10, 5, 12, 15, tzinfo=timezone.utc)
        src._cache["231747"] = {"price": 1, "ts": None, "fetched_at": (run_start - timedelta(minutes=10)).isoformat()}
        self.assertIsNone(src._cache_fresh(231747, run_start))


if __name__ == "__main__":
    unittest.main()
