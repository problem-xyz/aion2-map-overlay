"""Screen capture: dxcam where it works, mss everywhere else."""

import contextlib
import logging

import numpy as np

try:
    import dxcam  # Desktop Duplication API -- the fast capture path on Windows

    _dxcam_error = None
except Exception as e:  # noqa: BLE001 -- the module may be missing or fail to initialise
    dxcam = None
    _dxcam_error = e

import mss

log = logging.getLogger(__name__)


class Capture:
    """One rectangular region of the primary monitor, grabbed through the best backend available.

    dxcam is used when an output matching the primary monitor can be opened, mss otherwise;
    `backend` says which one won. The instance owns OS resources: it is built, used and closed
    on the engine thread, and `grab` may legitimately return no frame at all.
    """

    def __init__(self, region, screen_size=None) -> None:
        self.region = dict(region)
        self.cam = None
        self.sct = None
        if dxcam is not None:
            self.cam = self._open_dxcam(screen_size)
        if self.cam is None:
            self.sct = mss.mss()
        self.backend = "dxcam" if self.cam is not None else "mss"
        # Which backend won is worth a line either way: a build that quietly loses dxcam is
        # simply slower, and without this the only evidence is the frame rate.
        if self.cam is not None:
            log.info("capture backend: dxcam")
        elif dxcam is None:
            log.warning("capture backend: mss -- dxcam did not import (%s)", _dxcam_error)
        else:
            log.warning("capture backend: mss -- no dxcam output matched the primary monitor")

    @staticmethod
    def _open_dxcam(screen_size):
        """Open the dxcam output whose size matches the primary monitor.

        Output indexes do not follow the desktop layout, so the first output that opens may be
        another monitor, and the region coordinates only mean anything on the primary one.
        Returns None when nothing matches, which sends the caller to mss.
        """
        for idx in range(4):
            try:
                # Called only once dxcam has imported.
                cam = dxcam.create(output_idx=idx, output_color="BGRA")  # pyright: ignore[reportOptionalMemberAccess]
            except Exception:  # noqa: BLE001
                continue
            if cam is None:
                continue
            if screen_size is None or (cam.width, cam.height) == tuple(screen_size):
                return cam
            with contextlib.suppress(Exception):
                cam.release()
        return None

    def grab(self):
        """A BGRA frame (H, W, 4), or None when dxcam has nothing new since the last call."""
        r = self.region
        if self.cam is not None:
            box = (r["left"], r["top"], r["left"] + r["width"], r["top"] + r["height"])
            return self.cam.grab(region=box)
        # __init__ opens mss whenever it has no dxcam output.
        return np.asarray(self.sct.grab(r))  # pyright: ignore[reportOptionalMemberAccess]

    def close(self) -> None:
        if self.cam is not None:
            with contextlib.suppress(Exception):
                self.cam.release()
        if self.sct is not None:
            self.sct.close()
