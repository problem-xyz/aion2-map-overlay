"""Which copy of the timers' data is used, and what a fetch may and may not replace.

The network is a fake transport throughout: 304, a newer file, an older one, a broken one, a
foreign one, a failure. In every bad case the copy in use stays as it was.
"""

import json
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.timers_data import TimersDataService
from map_overlay.core.paths import resource_path
from map_overlay.store.timers import TimersError
from map_overlay.timers.data import MAX_BYTES, Fetched, FetchError, TimersStore, http_transport


def bundled(name: str) -> dict[str, Any]:
    return json.loads(resource_path(f"assets/timers/{name}").read_text(encoding="utf-8"))


def body(doc: dict[str, Any]) -> bytes:
    return json.dumps(doc).encode()


def newer_schedule() -> dict[str, Any]:
    doc = bundled("schedule.json")
    doc["updatedAt"] = "2099-01-01"
    doc["events"][0]["durationMinutes"] = 45
    return doc


def newer_bosses() -> dict[str, Any]:
    doc = bundled("world-bosses.json")
    doc["readAt"] = "2099-01-01T00:00:00Z"
    return doc


class FakeNet:
    """Answers by file name; records each request's ETag."""

    def __init__(self, answers: dict[str, Fetched | Exception]) -> None:
        self.answers = answers
        self.asked: list[tuple[str, str | None]] = []

    def __call__(self, url: str, etag: str | None) -> Fetched:
        name = url.rsplit("/", 1)[-1]
        self.asked.append((name, etag))
        answer = self.answers[name]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def store(tmp_path: Path) -> TimersStore:
    return TimersStore(tmp_path, base_url="https://example.test/timers/")


def test_with_nothing_fetched_the_bundled_copies_are_used(store: TimersStore) -> None:
    data = store.current()
    assert data.schedule and data.schedule.updated_at == bundled("schedule.json")["updatedAt"]
    assert data.bosses and len(data.bosses.bosses) == 24


def test_a_newer_schedule_is_taken_and_kept(store: TimersStore) -> None:
    net = FakeNet({"schedule.json": Fetched(body(newer_schedule()), '"v2"')})
    assert store.refresh("schedule", net)
    data = store.current()
    assert data.schedule and data.schedule.updated_at == "2099-01-01"
    assert data.schedule.events[0].duration_min == 45
    assert json.loads((store.dir / "etags.json").read_text())["schedule"] == '"v2"'


def test_the_held_etag_is_sent_and_304_changes_nothing(store: TimersStore) -> None:
    store.refresh("bosses", FakeNet({"world-bosses.json": Fetched(body(newer_bosses()), "b1")}))
    net = FakeNet({"world-bosses.json": Fetched(None, "b1")})
    assert not store.refresh("bosses", net)
    assert net.asked == [("world-bosses.json", "b1")]


def test_no_etag_is_sent_when_the_file_it_belongs_to_is_gone(store: TimersStore) -> None:
    store.refresh("bosses", FakeNet({"world-bosses.json": Fetched(body(newer_bosses()), "b1")}))
    (store.dir / "world-bosses.json").unlink()
    net = FakeNet({"world-bosses.json": Fetched(None, None)})
    store.refresh("bosses", net)
    assert net.asked == [("world-bosses.json", None)]


def test_a_file_older_than_the_bundled_copy_is_not_taken(store: TimersStore) -> None:
    old = bundled("world-bosses.json")
    old["readAt"] = "2020-01-01T00:00:00Z"
    assert not store.refresh("bosses", FakeNet({"world-bosses.json": Fetched(body(old), "x")}))
    assert not (store.dir / "world-bosses.json").exists()


def test_a_correction_that_moves_the_reading_back_still_replaces_the_fetched_copy(
    store: TimersStore,
) -> None:
    late = newer_bosses()
    late["readAt"] = "2099-01-01T00:00:45Z"
    assert store.refresh("bosses", FakeNet({"world-bosses.json": Fetched(body(late), "a")}))
    fixed = newer_bosses()
    fixed["readAt"] = "2099-01-01T00:00:10Z"
    assert store.refresh("bosses", FakeNet({"world-bosses.json": Fetched(body(fixed), "b")}))
    data = store.current()
    assert data.bosses and data.bosses.read_at.second == 10


def test_a_field_added_without_a_new_reading_is_taken(store: TimersStore) -> None:
    marked = bundled("world-bosses.json")
    marked["bosses"][0]["drops"] = ["relic"]
    assert store.refresh("bosses", FakeNet({"world-bosses.json": Fetched(body(marked), "m")}))
    data = store.current()
    assert data.bosses and data.bosses.bosses[0].drops == ("relic",), "a tie goes to the fetched"
    again = FakeNet({"world-bosses.json": Fetched(body(marked), None)})
    assert not store.refresh("bosses", again), "the same file again is nothing new"


@pytest.mark.parametrize(
    "payload",
    [
        b"<html>rate limited</html>",
        body({"format": "map-overlay-route", "version": 1}),
        body({**newer_schedule(), "version": 2}),
        body({**newer_schedule(), "regions": []}),
    ],
)
def test_a_broken_or_foreign_file_is_refused_and_nothing_changes(
    store: TimersStore, payload: bytes
) -> None:
    before = store.current()
    with pytest.raises(TimersError):
        store.refresh("schedule", FakeNet({"schedule.json": Fetched(payload, "x")}))
    assert store.current() == before
    assert not (store.dir / "schedule.json").exists()


def test_after_an_app_update_a_newer_bundled_copy_wins(store: TimersStore) -> None:
    stale = bundled("schedule.json")
    stale["updatedAt"] = "2000-01-01"
    store.dir.mkdir(parents=True)
    (store.dir / "schedule.json").write_text(json.dumps(stale), encoding="utf-8")
    data = store.current()
    assert data.schedule and data.schedule.updated_at == bundled("schedule.json")["updatedAt"]


def test_a_damaged_cached_file_falls_back_to_the_bundled(store: TimersStore) -> None:
    store.dir.mkdir(parents=True)
    (store.dir / "world-bosses.json").write_text("{ not json", encoding="utf-8")
    data = store.current()
    assert data.bosses and data.bosses.read_at.year == 2026


# ---------- the service: threads, timers and what reaches the GUI thread ----------


def wait_for(service: TimersDataService, timeout_s: float = 5) -> None:
    thread = service._thread
    if thread is not None:
        thread.join(timeout_s)
    for _ in range(20):
        QCoreApplication.processEvents()
        if not service.busy:
            return


@pytest.fixture
def service_for(
    qapp: QApplication, store: TimersStore
) -> Iterator[Callable[[FakeNet], TimersDataService]]:
    made: list[TimersDataService] = []

    def make(net: FakeNet) -> TimersDataService:
        s = TimersDataService(store, net, first_check_ms=10**9, interval_ms=10**9)
        made.append(s)
        return s

    yield make
    for s in made:
        s.close()
        s.deleteLater()


def test_a_fetch_that_takes_a_newer_copy_says_so(
    service_for: Callable[[FakeNet], TimersDataService],
) -> None:
    service = service_for(
        FakeNet(
            {
                "schedule.json": Fetched(body(newer_schedule()), "s"),
                "world-bosses.json": Fetched(None, None),
            }
        )
    )
    seen: list[Any] = []
    service.changed.connect(seen.append)
    assert service.refresh()
    wait_for(service)
    assert len(seen) == 1
    assert service.data.schedule and service.data.schedule.updated_at == "2099-01-01"


def test_a_failed_check_is_quiet_unless_the_user_asked(
    service_for: Callable[[FakeNet], TimersDataService],
) -> None:
    down = FetchError("offline")
    service = service_for(FakeNet({"schedule.json": down, "world-bosses.json": down}))
    codes: list[str] = []
    service.failed.connect(codes.append)
    service.refresh(manual=False)
    wait_for(service)
    assert codes == []
    service.refresh(manual=True)
    wait_for(service)
    assert codes == ["timers.fetch_failed"]
    assert service.data.schedule is not None, "the bundled copy stays in use"


def test_with_fetching_off_only_a_request_by_hand_fetches(
    service_for: Callable[[FakeNet], TimersDataService],
) -> None:
    net = FakeNet({"schedule.json": Fetched(None, None), "world-bosses.json": Fetched(None, None)})
    service = service_for(net)
    service.set_enabled(False)
    assert not service.refresh(manual=False)
    assert net.asked == []
    assert service.refresh(manual=True)
    wait_for(service)
    assert len(net.asked) == 2


def test_one_fetch_at_a_time(service_for: Callable[[FakeNet], TimersDataService]) -> None:
    net = FakeNet({"schedule.json": Fetched(None, None), "world-bosses.json": Fetched(None, None)})
    service = service_for(net)
    assert service.refresh()
    assert not service.refresh()
    wait_for(service)
    assert service.refresh()
    wait_for(service)


# ---------- the real transport, against a local server ----------


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.endswith("/broken"):
            self.send_response(500)
            self.end_headers()
            return
        if self.headers.get("If-None-Match") == '"one"':
            self.send_response(304)
            self.end_headers()
            return
        payload = b"x" * (MAX_BYTES + 10) if self.path.endswith("/big") else b'{"ok": true}'
        self.send_response(200)
        self.send_header("ETag", '"one"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        """Quiet: the test output is not the place for a request log."""


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()


def test_the_transport_returns_the_body_and_etag(server: str) -> None:
    got = http_transport(f"{server}/timers/schedule.json", None)
    assert got == Fetched(b'{"ok": true}', '"one"')


def test_the_transport_takes_304_as_nothing_new(server: str) -> None:
    assert http_transport(f"{server}/timers/schedule.json", '"one"') == Fetched(None, '"one"')


def test_the_transport_refuses_errors_and_oversized_bodies(server: str) -> None:
    with pytest.raises(FetchError, match="HTTP 500"):
        http_transport(f"{server}/broken", None)
    with pytest.raises(FetchError, match="larger than"):
        http_transport(f"{server}/big", None)
    with pytest.raises(FetchError):
        http_transport("http://127.0.0.1:9/nothing-listens-here", None)


def test_a_closed_service_starts_no_fetch(
    service_for: Callable[[FakeNet], TimersDataService],
) -> None:
    net = FakeNet({"schedule.json": Fetched(None, None), "world-bosses.json": Fetched(None, None)})
    service = service_for(net)
    service.close()
    assert not service.refresh(manual=True)
    assert net.asked == []
