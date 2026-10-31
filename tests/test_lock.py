import datetime as dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import checks
from app.enforcer import Enforcer, kill_process, run_loop, running_processes
from app.server import LockServer
from app.service import LockService

ANKI = {
    "profile": "x",
    "decks": ["Sprachen", "Spanisch"],
    "new_cards": 10,
    "review_cap": 100,
    "max_minutes": 30,
    "min_answer_ms": 1000,
}
CONFIG = {
    "day_rollover_hour": 4,
    "anki": ANKI,
    "leetcode": {"username": "someone"},
    "reading": {"minutes": 20, "min_note_chars": 20},
    "joker": {"per_week": 1},
}
NOW = dt.datetime(2026, 10, 31, 12, 0)
CREATED = dt.datetime(2026, 10, 1, 4, 0)
ANKI_TODAY = 30
DECKS = {1: "Sprachen\x1fRussisch", 2: "Spanisch", 3: "Archiv\x1fAlt", 4: "Sprachenzentrum"}
SCHEMA = """
create table col (crt integer);
create table decks (id integer, name text);
create table cards (id integer, did integer, odid integer, queue integer, due integer, odue integer);
create table revlog (id integer, cid integer, ease integer, time integer);
"""


class AnkiFixture:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA)
        self.db.execute("insert into col values (?)", (int(CREATED.timestamp()),))
        self.db.executemany("insert into decks values (?, ?)", DECKS.items())
        self.next_card = 1
        self.next_log = int(NOW.timestamp() * 1000) - 3_000_000

    def card(self, deck=1, queue=2, due=ANKI_TODAY + 5, odid=0, odue=0):
        card = self.next_card
        self.next_card += 1
        self.db.execute("insert into cards values (?, ?, ?, ?, ?, ?)", (card, deck, odid, queue, due, odue))
        return card

    def log(self, card, when=None, ease=3, taken_ms=5000):
        self.next_log += 1
        entry = int(when.timestamp() * 1000) if when else self.next_log
        self.db.execute("insert into revlog values (?, ?, ?, ?)", (entry, card, ease, taken_ms))

    def new_today(self, count, deck=1):
        for _ in range(count):
            self.log(self.card(deck))

    def reviewed_today(self, count, deck=1):
        for _ in range(count):
            card = self.card(deck)
            self.log(card, when=NOW - dt.timedelta(days=3))
            self.log(card)

    def evaluate(self):
        return checks.evaluate_anki(self.db, ANKI, NOW, 4)


class AnkiRuleTest(unittest.TestCase):
    def test_nothing_learned_is_open_even_without_due_cards(self):
        self.assertFalse(AnkiFixture().evaluate()["done"])

    def test_open_while_new_cards_are_missing(self):
        fixture = AnkiFixture()
        fixture.card(queue=0)
        fixture.new_today(9)
        result = fixture.evaluate()
        self.assertFalse(result["done"])
        self.assertIn("9/10 neue", result["detail"])

    def test_ten_new_and_no_reviews_due_is_done(self):
        fixture = AnkiFixture()
        fixture.card(queue=0)
        fixture.new_today(10)
        self.assertTrue(fixture.evaluate()["done"])

    def test_large_backlog_is_capped_at_review_limit(self):
        fixture = AnkiFixture()
        for _ in range(400):
            fixture.card(due=ANKI_TODAY - 2)
        fixture.new_today(10)
        fixture.reviewed_today(99)
        self.assertFalse(fixture.evaluate()["done"])
        fixture.reviewed_today(1)
        result = fixture.evaluate()
        self.assertTrue(result["done"])
        self.assertIn("100/100 Wiederholungen", result["detail"])

    def test_time_cap_ends_the_day(self):
        fixture = AnkiFixture()
        for _ in range(50):
            fixture.card(due=ANKI_TODAY)
        for _ in range(31):
            fixture.log(fixture.card(), taken_ms=60000)
        fixture.card(queue=0)
        self.assertTrue(fixture.evaluate()["done"])

    def test_other_decks_neither_count_nor_block(self):
        fixture = AnkiFixture()
        for _ in range(100):
            fixture.card(deck=3, due=ANKI_TODAY)
        fixture.new_today(10, deck=3)
        fixture.new_today(10, deck=4)
        self.assertFalse(fixture.evaluate()["done"])
        fixture.new_today(10, deck=2)
        self.assertTrue(fixture.evaluate()["done"])

    def test_flicked_answers_do_not_count(self):
        fixture = AnkiFixture()
        fixture.card(queue=0)
        for _ in range(10):
            fixture.log(fixture.card(), taken_ms=300)
        self.assertFalse(fixture.evaluate()["done"])

    def test_repeating_one_card_counts_once(self):
        fixture = AnkiFixture()
        fixture.card(queue=0)
        card = fixture.card()
        for _ in range(10):
            fixture.log(card)
        self.assertIn("1/10 neue", fixture.evaluate()["detail"])

    def test_reviews_before_rollover_belong_to_yesterday(self):
        fixture = AnkiFixture()
        fixture.log(fixture.card(), when=dt.datetime(2026, 10, 31, 3, 59))
        fixture.log(fixture.card(), when=dt.datetime(2026, 10, 31, 4, 1))
        self.assertIn("1/10 neue", fixture.evaluate()["detail"])

    def test_filtered_deck_cards_count_for_their_home_deck(self):
        fixture = AnkiFixture()
        fixture.card(deck=3, odid=1, queue=2, due=-100, odue=ANKI_TODAY)
        fixture.new_today(1)
        self.assertIn("1/10 neue Wörter · 0/1 Wiederholungen", fixture.evaluate()["detail"])

    def test_manual_reschedules_are_ignored(self):
        fixture = AnkiFixture()
        fixture.log(fixture.card(), ease=0)
        self.assertIn("0/10 neue", fixture.evaluate()["detail"])

    def test_copy_of_exclusively_locked_wal_database_is_readable(self):
        # Same pragmas Anki uses while a collection is open.
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "collection.anki2")
        db = sqlite3.connect(path)
        try:
            db.execute("pragma locking_mode = exclusive")
            db.execute("pragma journal_mode = wal")
            db.executescript(SCHEMA)
            db.execute("insert into col values (?)", (int(CREATED.timestamp()),))
            db.execute("insert into decks values (1, 'Sprachen')")
            db.execute("insert into cards values (1, 1, 0, 2, 999, 0)")
            db.execute("insert into revlog values (?, 1, 3, 5000)", (int(NOW.timestamp() * 1000),))
            db.commit()
            with self.assertRaises(sqlite3.OperationalError):
                other = sqlite3.connect(path, timeout=0)
                try:
                    other.execute("select crt from col").fetchone()
                finally:
                    other.close()
            result = checks.check_anki(path, ANKI, NOW, 4)
            self.assertIn("1/10 neue", result["detail"])
        finally:
            db.close()
            shutil.rmtree(tmp, ignore_errors=True)


class LeetCodeTest(unittest.TestCase):
    start = dt.datetime(2026, 10, 31, 4, 0)

    def payload(self, *moments):
        submissions = [{"title": f"A{i}", "timestamp": str(int(m.timestamp()))} for i, m in enumerate(moments)]
        return {"data": {"recentAcSubmissionList": submissions}}

    def test_solution_today_counts(self):
        result = checks.parse_leetcode(self.payload(dt.datetime(2026, 10, 31, 4, 0)), self.start)
        self.assertTrue(result["done"])

    def test_solution_before_rollover_does_not_count(self):
        result = checks.parse_leetcode(self.payload(dt.datetime(2026, 10, 31, 3, 59)), self.start)
        self.assertFalse(result["done"])

    def test_unknown_user_is_an_error(self):
        with self.assertRaises(ValueError):
            checks.parse_leetcode({"data": {"recentAcSubmissionList": None}}, self.start)


class Clock:
    def __init__(self, moment=NOW):
        self.value = moment.timestamp()

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.clock = Clock()
        self.anki = {"done": False, "detail": "offen", "error": None}
        self.leetcode = {"done": False, "detail": "offen", "error": None}
        self.leetcode_calls = 0
        self.service = self.make_service()

    def make_service(self):
        return LockService(CONFIG, self.dir, clock=self.clock,
                           anki_check=lambda now: self.anki, leetcode_check=self.fake_leetcode)

    def fake_leetcode(self, username, start):
        self.leetcode_calls += 1
        if isinstance(self.leetcode, Exception):
            raise self.leetcode
        return self.leetcode

    def read_fully(self):
        self.service.start_reading()
        self.clock.advance(20 * 60)
        self.service.finish_reading("Kapitel drei über Graphen gelesen.")

    def test_all_three_unlock(self):
        self.assertFalse(self.service.status()["unlocked"])
        self.anki = {"done": True, "detail": "ok", "error": None}
        self.assertFalse(self.service.status()["unlocked"])
        self.leetcode = {"done": True, "detail": "ok", "error": None}
        self.service.status(refresh=True)
        self.clock.advance(10)
        self.assertFalse(self.service.status(refresh=True)["unlocked"])
        self.read_fully()
        self.assertTrue(self.service.status()["unlocked"])

    def test_timer_must_run_out(self):
        with self.assertRaisesRegex(ValueError, "Timer"):
            self.service.finish_reading("Ein viel zu früher langer Satz zum Buch.")
        self.service.start_reading()
        self.clock.advance(19 * 60)
        with self.assertRaisesRegex(ValueError, "Timer"):
            self.service.finish_reading("Ein viel zu früher langer Satz zum Buch.")

    def test_restart_does_not_reset_timer(self):
        self.service.start_reading()
        self.clock.advance(600)
        self.assertEqual(self.service.start_reading()["remaining_seconds"], 600)

    def test_timer_survives_restart_of_service(self):
        self.service.start_reading()
        self.clock.advance(600)
        self.assertEqual(self.make_service().status()["checks"]["reading"]["remaining_seconds"], 600)

    def test_note_must_be_real(self):
        self.service.start_reading()
        self.clock.advance(20 * 60)
        with self.assertRaisesRegex(ValueError, "20 Zeichen"):
            self.service.finish_reading("   kurz      ")
        self.assertFalse(self.service.status()["checks"]["reading"]["done"])

    def test_note_is_logged(self):
        self.read_fully()
        with open(os.path.join(self.dir, "reading_log.jsonl"), encoding="utf-8") as file:
            self.assertEqual(json.loads(file.readline())["note"], "Kapitel drei über Graphen gelesen.")

    def test_done_stays_done_when_anki_later_fails(self):
        self.anki = {"done": True, "detail": "10/10", "error": None}
        self.service.status()
        self.anki = {"done": False, "detail": "x", "error": None}
        self.assertTrue(self.service.status()["checks"]["anki"]["done"])

    def test_new_day_locks_again_at_rollover(self):
        self.anki = self.leetcode = {"done": True, "detail": "ok", "error": None}
        self.service.status()
        self.read_fully()
        self.assertTrue(self.service.status()["unlocked"])
        self.clock.value = dt.datetime(2026, 11, 1, 3, 59).timestamp()
        self.assertTrue(self.service.status()["unlocked"])
        self.anki = self.leetcode = {"done": False, "detail": "offen", "error": None}
        self.clock.value = dt.datetime(2026, 11, 1, 4, 0).timestamp()
        status = self.service.status()
        self.assertFalse(status["unlocked"])
        self.assertEqual(status["checks"]["reading"]["state"], "idle")

    def test_anki_failure_keeps_lock(self):
        def fail(now):
            raise OSError("kaputt")
        self.service.anki_check = fail
        status = self.service.status()
        self.assertFalse(status["unlocked"])
        self.assertEqual(status["checks"]["anki"]["error"], "kaputt")

    def test_leetcode_failure_keeps_lock(self):
        self.leetcode = OSError("offline")
        status = self.service.status()
        self.assertFalse(status["unlocked"])
        self.assertEqual(status["checks"]["leetcode"]["error"], "offline")

    def test_leetcode_is_cached(self):
        self.service.status()
        self.service.status()
        self.clock.advance(60)
        self.service.status()
        self.assertEqual(self.leetcode_calls, 1)
        self.service.status(refresh=True)
        self.assertEqual(self.leetcode_calls, 2)
        self.clock.advance(1)
        self.service.status(refresh=True)
        self.assertEqual(self.leetcode_calls, 2)

    def test_enforcer_status_uses_no_network(self):
        self.service.status(network=False)
        self.assertEqual(self.leetcode_calls, 0)


class JokerTest(ServiceTest):
    # NOW is Saturday, 2026-10-31.
    def at(self, *moment):
        self.clock.value = dt.datetime(*moment).timestamp()

    def test_joker_unlocks_only_today(self):
        self.service.use_joker("krank")
        status = self.service.status()
        self.assertTrue(status["unlocked"])
        self.assertEqual(status["joker"]["reason"], "krank")
        self.at(2026, 11, 1, 3, 59)
        self.assertTrue(self.service.status()["unlocked"])
        self.at(2026, 11, 1, 4, 0)
        self.assertFalse(self.service.status()["unlocked"])

    def test_second_joker_in_same_week_is_refused(self):
        self.service.use_joker("krank")
        self.at(2026, 11, 1, 12, 0)
        self.assertEqual(self.service.status()["joker"]["left"], 0)
        with self.assertRaisesRegex(ValueError, "verbraucht"):
            self.service.use_joker("nochmal")
        self.assertFalse(self.service.status()["unlocked"])

    def test_new_week_brings_new_joker_at_rollover(self):
        self.service.use_joker("krank")
        self.at(2026, 11, 2, 3, 59)
        self.assertEqual(self.service.status()["joker"]["left"], 0)
        self.at(2026, 11, 2, 4, 0)
        self.assertEqual(self.service.status()["joker"]["left"], 1)
        self.service.use_joker("Klausur")
        self.assertTrue(self.service.status()["unlocked"])

    def test_using_it_twice_today_costs_one(self):
        self.service.use_joker("krank")
        self.service.use_joker("anders")
        status = self.service.status()["joker"]
        self.assertEqual(status["reason"], "krank")
        self.assertEqual(status["left"], 0)

    def test_reason_is_required(self):
        with self.assertRaisesRegex(ValueError, "warum"):
            self.service.use_joker("  a  ")
        self.assertEqual(self.service.status()["joker"]["left"], 1)

    def test_joker_is_not_spent_when_everything_is_done(self):
        self.anki = self.leetcode = {"done": True, "detail": "ok", "error": None}
        self.service.status()
        self.read_fully()
        with self.assertRaisesRegex(ValueError, "erledigt"):
            self.service.use_joker("krank")
        self.assertEqual(self.service.status()["joker"]["left"], 1)

    def test_used_joker_survives_restart(self):
        self.service.use_joker("krank")
        self.at(2026, 11, 1, 12, 0)
        self.service.status()
        self.assertEqual(self.make_service().status()["joker"]["left"], 0)

    def test_state_file_from_before_jokers_still_works(self):
        with open(os.path.join(self.dir, "state.json"), "w", encoding="utf-8") as file:
            json.dump({"day": "2026-10-31", "done": {}, "reading": {}}, file)
        service = self.make_service()
        self.assertEqual(service.status()["joker"]["left"], 1)
        service.use_joker("krank")
        self.assertTrue(service.status()["unlocked"])


class EnforcerTest(unittest.TestCase):
    def make(self, running):
        self.killed = []
        return Enforcer(["LeagueClient.exe", "League of Legends.exe"], "League of Legends.exe",
                        lister=lambda: set(running), killer=self.killed.append)

    def test_locked_closes_client(self):
        self.make({"leagueclient.exe", "chrome.exe"}).tick(False)
        self.assertEqual(self.killed, ["LeagueClient.exe"])

    def test_unlocked_closes_nothing(self):
        self.make({"leagueclient.exe"}).tick(True)
        self.assertEqual(self.killed, [])

    def test_allowed_match_survives_rollover(self):
        enforcer = self.make({"leagueclient.exe", "league of legends.exe"})
        enforcer.tick(True)
        enforcer.tick(False)
        self.assertEqual(self.killed, [])

    def test_client_closes_once_match_ended(self):
        running = {"leagueclient.exe", "league of legends.exe"}
        self.killed = []
        enforcer = Enforcer(["LeagueClient.exe"], "League of Legends.exe",
                            lister=lambda: running, killer=self.killed.append)
        enforcer.tick(True)
        enforcer.tick(False)
        running.discard("league of legends.exe")
        enforcer.tick(False)
        self.assertEqual(self.killed, ["LeagueClient.exe"])

    def test_match_started_while_locked_is_closed(self):
        self.make({"league of legends.exe"}).tick(False)
        self.assertEqual(self.killed, ["League of Legends.exe"])

    def test_real_process_listing_and_kill_on_dummy(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        name = "productivitylockdummy.exe"
        exe = os.path.join(tmp, name)
        shutil.copy(os.path.join(os.environ["SystemRoot"], "System32", "PING.EXE"), exe)
        process = subprocess.Popen([exe, "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL)
        self.addCleanup(process.kill)
        self.assertIn(name, running_processes())
        kill_process(name)
        process.wait(timeout=10)
        self.assertNotIn(name, running_processes())


class RunLoopTest(unittest.TestCase):
    def run_loop_once(self, dry_run):
        killed = []
        opened = []
        stop = threading.Event()
        enforcer = Enforcer(["LeagueClient.exe"], "League of Legends.exe",
                            lister=lambda: {"leagueclient.exe"}, killer=killed.append)

        class Locked:
            def status(self, network):
                return {"unlocked": False}

        with mock.patch("app.enforcer.LOOP_SECONDS", 0.01), \
                mock.patch("app.enforcer.webbrowser.open", opened.append):
            thread = threading.Thread(target=run_loop, args=(Locked(), enforcer, "page", dry_run, time.monotonic, stop))
            thread.start()
            time.sleep(0.2)
            stop.set()
            thread.join(timeout=5)
        return killed, opened

    def test_dry_run_never_closes_anything(self):
        self.assertEqual(self.run_loop_once(dry_run=True), ([], []))

    def test_lock_closes_and_explains_once(self):
        killed, opened = self.run_loop_once(dry_run=False)
        self.assertGreater(len(killed), 1)
        self.assertEqual(opened, ["page"])


class ServerTest(unittest.TestCase):
    PORT = 47699

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        ready = {"done": False, "detail": "offen", "error": None}
        self.service = LockService(CONFIG, self.dir, anki_check=lambda now: ready,
                                   leetcode_check=lambda user, start: ready)
        static = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extension")
        self.server = LockServer(self.service, static, port=self.PORT)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, method="GET", body=None, origin=None, host=None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.PORT}{path}", method=method,
                                         data=json.dumps(body).encode() if body is not None else None)
        request.add_header("Host", host or f"127.0.0.1:47615")
        if origin:
            request.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers

    def test_status_is_locked(self):
        code, body, _ = self.request("/status")
        self.assertEqual(code, 200)
        self.assertFalse(json.loads(body)["unlocked"])

    def test_extension_origin_gets_cors(self):
        origin = "chrome-extension://abc"
        _, _, headers = self.request("/status", origin=origin)
        self.assertEqual(headers["Access-Control-Allow-Origin"], origin)

    def test_foreign_website_is_refused(self):
        code, _, _ = self.request("/reading/start", method="POST", body={}, origin="https://evil.example")
        self.assertEqual(code, 403)
        self.assertEqual(self.service.status()["checks"]["reading"]["state"], "idle")

    def test_joker_endpoint(self):
        self.assertEqual(self.request("/joker", method="POST", body={"reason": "x"})[0], 400)
        code, body, _ = self.request("/joker", method="POST", body={"reason": "krank"})
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["active"])

    def test_foreign_website_cannot_use_joker(self):
        code, _, _ = self.request("/joker", method="POST", body={"reason": "krank"}, origin="https://evil.example")
        self.assertEqual(code, 403)
        self.assertFalse(self.service.status()["joker"]["active"])

    def test_rebinding_host_is_refused(self):
        self.assertEqual(self.request("/status", host="evil.example:47615")[0], 403)

    def test_early_finish_returns_message(self):
        code, body, _ = self.request("/reading/finish", method="POST", body={"note": "x"})
        self.assertEqual(code, 400)
        self.assertIn("Timer", json.loads(body)["error"])

    def test_malformed_json_returns_400(self):
        request = urllib.request.Request(f"http://127.0.0.1:{self.PORT}/reading/finish", method="POST", data=b"{nope")
        request.add_header("Host", "127.0.0.1:47615")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)

    def test_lock_page_is_served(self):
        code, body, _ = self.request("/")
        self.assertEqual(code, 200)
        self.assertIn(b"locked.js", body)

    def test_unknown_static_path_is_404(self):
        self.assertEqual(self.request("/../config.json")[0], 404)

    def test_second_instance_cannot_bind(self):
        with self.assertRaises(OSError):
            LockServer(self.service, ".", port=self.PORT)


if __name__ == "__main__":
    unittest.main()
