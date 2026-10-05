"""Write assets/sounds/chime.wav, the timers' reminder chime, from nothing but arithmetic.

    uv run python scripts/make_chime.py

Two struck notes a major third apart, each a bell's partials dying away at their own rates, so
the sound is the project's own and carries no licence of anyone else's. 44.1 kHz, mono, 16-bit
PCM: the format winsound plays without a codec. Run it again only to change the sound.
"""

import io
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sounds" / "chime.wav"

RATE = 44_100
LENGTH_S = 1.6
# (onset in seconds, fundamental in Hz): C6, then E6 a moment later
NOTES = ((0.0, 1046.5), (0.16, 1318.5))
# A bell's partials: (ratio to the fundamental, loudness, how fast it dies, per second)
PARTIALS = ((1.0, 1.0, 3.2), (2.0, 0.45, 5.0), (3.0, 0.22, 7.5), (4.2, 0.12, 10.0))
ATTACK_S = 0.004  # a few milliseconds of rise, so the strike does not click
PEAK = 0.6  # of full scale: loud enough, with room for the player's own volume above it


def chime() -> np.ndarray:
    t = np.arange(int(RATE * LENGTH_S)) / RATE
    out = np.zeros_like(t)
    for onset, base in NOTES:
        local = t - onset
        on = local >= 0
        env = np.where(on, 1.0, 0.0) * np.clip(local / ATTACK_S, 0.0, 1.0)
        for ratio, loud, decay in PARTIALS:
            out += (
                loud
                * env
                * np.exp(-decay * np.maximum(local, 0.0))
                * np.sin(2 * np.pi * base * ratio * np.maximum(local, 0.0))
            )
    return out / np.abs(out).max() * PEAK


def wav_bytes(samples: np.ndarray) -> bytes:
    pcm = np.round(samples * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(wav_bytes(chime()))
    print(f"{OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
