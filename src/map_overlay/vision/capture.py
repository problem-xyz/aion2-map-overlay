"""Screen capture: dxcam where it works, mss everywhere else.

On a monitor running in HDR, dxcam's 8-bit frames are clipped to a washed-out picture that the
tracker cannot match, so that case goes through capture_hdr's half-float duplication instead.
"""

import contextlib
import logging
from typing import ClassVar

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
    `backend` says which one won. "dxcam-hdr" is that same output in HDR, grabbed in half floats
    by `HdrGrabber` in place of the dxcam camera. The instance owns OS resources: it is built,
    used and closed on the engine thread, and `grab` may legitimately return no frame at all.
    """

    # Cleared, for the life of the process, on a machine where dxcam crashed it once
    # (see core/crash_guard.py). Set before the engine first runs.
    dxcam_allowed: ClassVar[bool] = True

    def __init__(self, region, screen_size=None) -> None:
        self.region = dict(region)
        self.cam = None
        self.hdr = None
        self.sct = None
        if dxcam is not None and self.dxcam_allowed:
            self.cam, output_idx = self._open_dxcam(screen_size)
            if self.cam is not None:
                self._switch_to_hdr(output_idx)
        if self.cam is None and self.hdr is None:
            self.sct = mss.mss()
        if self.hdr is not None:
            self.backend = "dxcam-hdr"
        else:
            self.backend = "dxcam" if self.cam is not None else "mss"
        # Which backend won is worth a line either way: a build that quietly loses dxcam is
        # simply slower, and without this the only evidence is the frame rate.
        if self.hdr is not None:
            log.info("capture backend: dxcam-hdr -- the monitor is in HDR, grabbing half floats")
        elif self.cam is not None:
            log.info("capture backend: dxcam")
        elif dxcam is None:
            log.warning("capture backend: mss -- dxcam did not import (%s)", _dxcam_error)
        elif not self.dxcam_allowed:
            log.warning("capture backend: mss -- dxcam is off since it crashed the app")
        else:
            log.warning("capture backend: mss -- no dxcam output matched the primary monitor")

    @staticmethod
    def _open_dxcam(screen_size):
        """Open the dxcam output whose size matches the primary monitor: (camera, output index).

        Output indexes do not follow the desktop layout, so the first output that opens may be
        another monitor, and the region coordinates only mean anything on the primary one.
        Returns (None, None) when nothing matches, which sends the caller to mss.
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
                return cam, idx
            with contextlib.suppress(Exception):
                cam.release()
        return None, None

    def _switch_to_hdr(self, output_idx) -> None:
        """Replace the dxcam camera by an HdrGrabber when its output is in HDR.

        The camera goes first, so that only one duplication of the output is open. Should the
        grabber fail to start, a fresh camera takes its place and the capture is what it was
        before HDR support: washed out, but running. Imported here, so that a failure in the
        HDR path can never cost the plain dxcam one.
        """
        try:
            from map_overlay.vision.capture_hdr import HdrGrabber, is_hdr  # noqa: PLC0415

            # dxcam 0.3.0 keeps the output and device it captures from here; see capture_hdr.
            output, device = self.cam._output, self.cam._device  # pyright: ignore[reportOptionalMemberAccess]
            if output.rotation_angle != 0 or not is_hdr(output):
                return
        except Exception:  # any failure here leaves the plain dxcam path
            log.warning("could not tell whether the monitor is in HDR", exc_info=True)
            return
        self.cam.release()  # pyright: ignore[reportOptionalMemberAccess]
        self.cam = None
        try:
            self.hdr = HdrGrabber(output, device)
        except Exception:  # any failure here leaves the plain dxcam path
            log.warning("HDR capture did not start; staying on 8-bit dxcam", exc_info=True)
            with contextlib.suppress(Exception):
                # Called only once dxcam has imported.
                self.cam = dxcam.create(output_idx=output_idx, output_color="BGRA")  # pyright: ignore[reportOptionalMemberAccess]

    def grab(self):
        """A BGRA frame (H, W, 4), or None when dxcam has nothing new since the last call."""
        r = self.region
        box = (r["left"], r["top"], r["left"] + r["width"], r["top"] + r["height"])
        if self.hdr is not None:
            return self.hdr.grab(box)
        if self.cam is not None:
            return self.cam.grab(region=box)
        # __init__ opens mss whenever it has no dxcam output.
        return np.asarray(self.sct.grab(r))  # pyright: ignore[reportOptionalMemberAccess]

    def close(self) -> None:
        if self.hdr is not None:
            self.hdr.close()
        if self.cam is not None:
            with contextlib.suppress(Exception):
                self.cam.release()
        if self.sct is not None:
            self.sct.close()
