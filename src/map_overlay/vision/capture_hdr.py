"""Desktop Duplication in half floats, for a monitor running in HDR.

dxcam asks Desktop Duplication for B8G8R8A8 only. On an HDR desktop Windows produces that by
clipping the scRGB composition at 1.0, and the frame comes out washed out (see vision/hdr.py).
This asks for R16G16B16A16_FLOAT first, which DXGI grants when the desktop is composed in it, and
hands the half floats to `ScrgbToBgra`. B8G8R8A8 stays on the list, so a desktop that leaves HDR
mid-session still captures, as it did before.

Built on dxcam's device, output and COM interface definitions rather than a second copy of them.
Those are internals of the pinned dxcam version; a dxcam upgrade has to be checked against this.
"""

import ctypes
import logging
import time
from ctypes import wintypes
from typing import Any, cast

import comtypes
import numpy as np
from dxcam._libs.d3d11 import (
    D3D11_BOX,
    D3D11_CPU_ACCESS_READ,
    D3D11_TEXTURE2D_DESC,
    D3D11_USAGE_STAGING,
    DXGI_FORMAT_B8G8R8A8_UNORM,
    ID3D11Texture2D,
)
from dxcam._libs.dxgi import (
    DXGI_MAPPED_RECT,
    DXGI_OUTDUPL_FLAG_NONE,
    DXGI_OUTDUPL_FRAME_INFO,
    IDXGIOutput5,
    IDXGIOutputDuplication,
    IDXGIResource,
    IDXGISurface,
)

from map_overlay.vision.hdr import ScrgbToBgra

log = logging.getLogger(__name__)

DXGI_FORMAT_R16G16B16A16_FLOAT = 10
# The colour space of an output that Windows drives in HDR (HDR10: ST.2084 over BT.2020).
DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020 = 12
DXGI_ERROR_WAIT_TIMEOUT = 0x887A0027
DXGI_MAP_READ = 1
# How long to wait before trying to duplicate the output again after losing it. The loss comes
# from a mode switch, a secure desktop (UAC, Ctrl+Alt+Del) or a fullscreen app taking over, and
# duplicating again fails until that is over.
REOPEN_INTERVAL_S = 0.5


class _OutputDesc1(ctypes.Structure):
    """DXGI_OUTPUT_DESC1."""

    _fields_ = [
        ("DeviceName", wintypes.WCHAR * 32),
        ("DesktopCoordinates", wintypes.RECT),
        ("AttachedToDesktop", wintypes.BOOL),
        ("Rotation", wintypes.UINT),
        ("Monitor", wintypes.HMONITOR),
        ("BitsPerColor", wintypes.UINT),
        ("ColorSpace", wintypes.UINT),
        ("RedPrimary", ctypes.c_float * 2),
        ("GreenPrimary", ctypes.c_float * 2),
        ("BluePrimary", ctypes.c_float * 2),
        ("WhitePoint", ctypes.c_float * 2),
        ("MinLuminance", ctypes.c_float),
        ("MaxLuminance", ctypes.c_float),
        ("MaxFullFrameLuminance", ctypes.c_float),
    ]


class IDXGIOutput6(IDXGIOutput5):
    _iid_ = comtypes.GUID("{068346e8-aaec-4b84-add7-137f513f77a1}")
    _methods_ = [
        comtypes.STDMETHOD(comtypes.HRESULT, "GetDesc1", [ctypes.POINTER(_OutputDesc1)]),
        comtypes.STDMETHOD(
            comtypes.HRESULT, "CheckHardwareCompositionSupport", [ctypes.POINTER(wintypes.UINT)]
        ),
    ]


def _hresult(e: comtypes.COMError) -> int:
    return e.hresult & 0xFFFFFFFF


def is_hdr(output: Any) -> bool:
    """Whether Windows drives this dxcam `Output` in HDR. False when the system cannot say."""
    try:
        output6 = output.output.QueryInterface(IDXGIOutput6)
        desc = _OutputDesc1()
        output6.GetDesc1(ctypes.byref(desc))
    except comtypes.COMError, OSError:
        return False
    return desc.ColorSpace == DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020


class HdrGrabber:
    """Grabs a region of one output through Desktop Duplication, half floats preferred.

    Takes over the dxcam output and device it is given; the dxcam camera on that output has to be
    released first, so that only one duplication of it is open. Like `Capture`, it is built, used
    and closed on the engine thread.
    """

    def __init__(self, output: Any, device: Any) -> None:
        self._output = output
        self._device = device
        self._dup: Any = None
        self._stage: tuple[Any, Any] | None = None
        self._stage_key: tuple[int, int, int] | None = None
        self._next_open = 0.0
        self._convert = ScrgbToBgra()
        # The first duplication is allowed to fail loudly: the caller then stays on dxcam.
        self._open()

    @property
    def exposure(self) -> float | None:
        return self._convert.exposure

    def _open(self) -> None:
        output5 = self._output.output.QueryInterface(IDXGIOutput5)
        formats = (wintypes.UINT * 2)(DXGI_FORMAT_R16G16B16A16_FLOAT, DXGI_FORMAT_B8G8R8A8_UNORM)
        dup = ctypes.POINTER(IDXGIOutputDuplication)()
        output5.DuplicateOutput1(
            ctypes.cast(self._device.device, ctypes.c_void_p),
            DXGI_OUTDUPL_FLAG_NONE,
            len(formats),
            formats,
            ctypes.byref(dup),
        )
        self._dup = dup

    def _lost(self, e: comtypes.COMError) -> None:
        """The duplication is gone; drop it and try again after REOPEN_INTERVAL_S."""
        log.warning("HDR capture lost the output (HRESULT=0x%08X); reopening", _hresult(e))
        self._release_dup()
        self._next_open = time.monotonic() + REOPEN_INTERVAL_S

    def _reopen(self) -> bool:
        if time.monotonic() < self._next_open:
            return False
        try:
            self._open()
        except comtypes.COMError as e:
            log.debug("HDR capture reopen failed (HRESULT=0x%08X)", _hresult(e))
            self._next_open = time.monotonic() + REOPEN_INTERVAL_S
            return False
        return True

    def _stage_for(self, width: int, height: int, fmt: int) -> tuple[Any, Any]:
        """A CPU-readable texture of this size and format and its surface, kept while neither
        changes."""
        key = (width, height, fmt)
        if self._stage_key != key:
            self._release_stage()
            desc = D3D11_TEXTURE2D_DESC()
            desc.Width, desc.Height, desc.Format = width, height, fmt
            desc.MipLevels = desc.ArraySize = desc.SampleDesc.Count = 1
            desc.Usage = D3D11_USAGE_STAGING
            desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ
            texture: Any = ctypes.POINTER(ID3D11Texture2D)()
            self._device.device.CreateTexture2D(ctypes.byref(desc), None, ctypes.byref(texture))
            self._stage, self._stage_key = (texture, texture.QueryInterface(IDXGISurface)), key
        return cast(tuple[Any, Any], self._stage)

    def grab(self, box: tuple[int, int, int, int]) -> np.ndarray | None:
        """A BGRA frame (H, W, 4) of `box` (left, top, right, bottom), or None when none is new."""
        if self._dup is None and not self._reopen():
            return None
        dup: Any = self._dup
        info = DXGI_OUTDUPL_FRAME_INFO()
        resource: Any = ctypes.POINTER(IDXGIResource)()
        try:
            dup.AcquireNextFrame(0, ctypes.byref(info), ctypes.byref(resource))
        except comtypes.COMError as e:
            if _hresult(e) != DXGI_ERROR_WAIT_TIMEOUT:
                self._lost(e)
            return None
        try:
            texture = resource.QueryInterface(ID3D11Texture2D)
            desc = D3D11_TEXTURE2D_DESC()
            texture.GetDesc(ctypes.byref(desc))
            left, top, right, bottom = box
            width, height = right - left, bottom - top
            stage = self._stage_for(width, height, desc.Format)
            src = D3D11_BOX(left=left, top=top, front=0, right=right, bottom=bottom, back=1)
            self._device.im_context.CopySubresourceRegion(
                stage[0], 0, 0, 0, 0, texture, 0, ctypes.byref(src)
            )
        except comtypes.COMError as e:
            self._lost(e)
            return None
        finally:
            # Released as soon as the copy is queued, as dxcam does by default: holding it until
            # the next acquire costs frame pacing.
            self._release_frame()
        return self._read(stage, width, height, desc.Format)

    def _read(self, stage: tuple[Any, Any], width: int, height: int, fmt: int) -> np.ndarray | None:
        surface = stage[1]
        rect = DXGI_MAPPED_RECT()
        try:
            surface.Map(ctypes.byref(rect), DXGI_MAP_READ)
        except comtypes.COMError as e:
            self._lost(e)
            return None
        try:
            pixel = 8 if fmt == DXGI_FORMAT_R16G16B16A16_FLOAT else 4
            rows = np.ctypeslib.as_array(rect.pBits, shape=(height * rect.Pitch,))
            rows = rows.reshape(height, rect.Pitch)[:, : width * pixel]
            if fmt == DXGI_FORMAT_R16G16B16A16_FLOAT:
                return self._convert(rows.view(np.float16).reshape(height, width, 4))
            return rows.reshape(height, width, 4).copy()
        finally:
            surface.Unmap()

    def _release_frame(self) -> None:
        if self._dup is None:
            return
        try:
            self._dup.ReleaseFrame()
        except comtypes.COMError as e:
            log.debug("ReleaseFrame failed (HRESULT=0x%08X)", _hresult(e))

    # comtypes releases a COM pointer when the last Python reference to it goes, so dropping the
    # reference is the release; calling Release() as well would release it twice.
    def _release_dup(self) -> None:
        self._dup = None

    def _release_stage(self) -> None:
        self._stage, self._stage_key = None, None

    def close(self) -> None:
        self._release_stage()
        self._release_dup()
        self._convert.close()
