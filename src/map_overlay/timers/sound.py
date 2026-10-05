"""Playing a reminder's sound: a WAV at the user's volume, on a thread of its own. No Qt.

winsound is in the standard library, so the build carries no audio stack for a two-second
chime; QtMultimedia, which would, is excluded from it. winsound cannot play from memory without
blocking, so each sound plays on a daemon thread, and a new one cuts the last one short. The
volume is applied to the samples themselves, since winsound has no volume of its own.
"""

import contextlib
import io
import logging
import sys
import threading
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# What plays a WAV held in memory, blocking until it ends; a test hands in its own.
Play = Callable[[bytes], None]


def _winsound_play(data: bytes) -> None:
    import winsound  # noqa: PLC0415 -- Windows only

    winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)


def _winsound_stop() -> None:
    import winsound  # noqa: PLC0415 -- Windows only

    with contextlib.suppress(RuntimeError):
        winsound.PlaySound(None, 0)


def scaled(data: bytes, volume: float) -> bytes:
    """The WAV with its 16-bit samples scaled by volume, 0..1; other formats come back as is."""
    volume = max(0.0, min(1.0, float(volume)))
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        log.warning("not a WAV the volume can be set on: %s", e)
        return data
    if params.sampwidth != 2:
        return data
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) * volume
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setparams(params)
        w.writeframes(np.clip(samples, -32768, 32767).astype("<i2").tobytes())
    return out.getvalue()


class SoundPlayer:
    """One sound at a time, played off the GUI thread. Silent where winsound does not exist."""

    def __init__(self, play: Play | None = None, stop: Callable[[], None] | None = None) -> None:
        available = sys.platform == "win32"
        self._play = play or (_winsound_play if available else None)
        self._stop = stop or (_winsound_stop if available else None)
        self._cache: dict[Path, bytes] = {}

    def play(self, path: Path, volume: float) -> threading.Thread | None:
        """Start the file at the volume; the last sound, if still playing, stops first."""
        if self._play is None or volume <= 0:
            return None
        try:
            raw = self._cache.get(path) or path.read_bytes()
        except OSError:
            log.warning("reminder sound %s cannot be read", path)
            return None
        self._cache[path] = raw
        data = scaled(raw, volume)
        if self._stop is not None:
            self._stop()
        play = self._play
        thread = threading.Thread(
            target=self._run, args=(play, data), name="timers-sound", daemon=True
        )
        thread.start()
        return thread

    @staticmethod
    def _run(play: Play, data: bytes) -> None:
        try:
            play(data)
        except RuntimeError as e:  # winsound reports a device it cannot open this way
            log.warning("reminder sound did not play: %s", e)
