"""The steps plaque: a small always-on-top window listing the route's steps."""

import json

from PySide6.QtCore import Slot

from map_overlay.core.settings import STEPS_SIZE_SCALE, Region, plaque_scale
from map_overlay.i18n.catalog import current_language, t
from map_overlay.qt.plaque_window import PlaqueBridge, PlaqueWindow


def scale_region(region: Region, ratio: float) -> Region:
    """The plaque's rectangle at another zoom: the same top-left corner, the size times ratio."""
    return {
        "left": region["left"],
        "top": region["top"],
        "width": round(region["width"] * ratio),
        "height": round(region["height"] * ratio),
    }


class StepsBridge(PlaqueBridge):
    """The page's `steps` object. Its six slots and one signal are the frozen half of the UI
    contract: the plaque's page is built against these exact names. Five come from PlaqueBridge.
    """

    @Slot(int)
    def setHeight(self, height) -> None:
        """Read by nothing since api 18: the user sizes the plaque, and the page fits the rows."""


class WebStepsWindow(PlaqueWindow):
    """The steps plaque: the route's steps list, drawn by the page in its `#steps` mode.

    Everything native -- moving, sizing, pinning, the hotspot -- is PlaqueWindow's. This class
    holds the steps, how far along the route is, and the plaque's zoom.
    """

    # The size a plaque starts at, times the zoom. BASE_WIDTH is the old M, at a factor of 1.
    BASE_WIDTH = 430
    BASE_HEIGHT = 300
    SIZES = STEPS_SIZE_SCALE
    ORDER = ("s", "m", "l")
    # What the three old steps were drawn at, for a page from before the scale
    OLD_FACTORS = {"s": 0.85, "m": 1.0, "l": 1.25}
    MIN_WIDTH = 200
    MIN_HEIGHT = 90  # the head and one row, at a factor of 1
    BRIDGE = StepsBridge

    def __init__(self, dev=False) -> None:
        self._steps = []
        self._done = 0
        self._past = 0  # how many steps already passed the plaque keeps, as route_past
        self._title = ""
        super().__init__(page="steps", channel_name="steps", dev=dev)
        self.setWindowTitle(t("native.window.steps"))
        self._scale = plaque_scale(1.0)  # the factor drawn at, not the slider's value

    def set_steps(self, steps, done=0, title="") -> None:
        self._steps = list(steps or [])
        self._done = max(0, int(done))
        self._title = str(title or "")
        self._push()

    def set_past(self, past) -> None:
        """How many steps already passed stay on the list, faded, as they stay on the map."""
        past = max(0, int(past))
        if past != self._past:
            self._past = past
            self._push()

    def set_size(self, key) -> None:
        """One of the three old steps, as a scale."""
        if key in self.SIZES:
            self.set_scale(self.SIZES[key])

    def set_scale(self, setting) -> None:
        """The slider's value, steps_scale: the page draws at the factor it stands for.

        The window keeps its size here. Backend scales the stored rectangle with the zoom, so a
        plaque the user sized keeps its proportions.
        """
        scale = plaque_scale(float(setting))
        if scale == self._scale:
            return
        self._scale = scale
        self._push()

    def size_key(self):
        """The old step nearest the size drawn, for a page that only knows those."""
        return min(self.OLD_FACTORS, key=lambda k: abs(self.OLD_FACTORS[k] - self._scale))

    def has_steps(self):
        return any(s[0] > self._done for s in self._steps)

    def data_json(self):
        return json.dumps(
            {
                "steps": [
                    {
                        "n": n,
                        "text": t,
                        "color": c,
                        **({"icon": icon} if icon else {}),
                        **({"object": on} if on else {}),
                    }
                    for n, t, c, icon, on in self._steps
                ],
                "done": self._done,
                "past": self._past,
                "title": self._title,
                "size": self.size_key(),
                "scale": self._scale,
                "pinned": self._pinned,
                "grip": self.GRIP,  # api 18: the resize strips along the right and bottom edges
                # the step arrows: always offered, since progress always counts (api 16)
                "switch": True,
                "opacity": self._opacity,
                # The plaque is its own document and never sees getState, so the language it
                # should render in has to travel with its data.
                "language": current_language(),
            },
            ensure_ascii=False,
        )

    def retitle(self) -> None:
        """Re-read the title, and tell the page which language it is drawing in now.

        The plaque renders its own text, so a language change has to reach the page as
        data; it never sees getState.
        """
        self.setWindowTitle(t("native.window.steps"))
        self._push()
