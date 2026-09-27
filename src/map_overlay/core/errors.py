"""Domain failures, carried as a stable code plus parameters rather than a sentence.

A message baked into a raise cannot be translated, cannot be matched on by the UI, and drifts
the moment someone rewords it. The code is the contract; the English sentence is generated
from it in i18n/catalog.py, and the other languages come from locales/ without touching this layer.

OSError is deliberately *not* one of these. It is wrapped at the service boundary into a code
that says what the app was doing -- route.save_failed -- because "permission denied" alone
tells the user nothing about which of their actions just did not happen.
"""

from typing import Any


class AppError(Exception):
    """Base for anything the user should be told about in their own words.

    code is the stable dotted identifier the UI translates and params are its substitutions;
    the facade turns the pair into a notify {level, code, params, text}. Never put str(e) in
    front of the user -- it is a debugging aid, and the text in that notice is only the English
    fallback for a UI that could not translate the code itself.
    """

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params

    def __str__(self) -> str:
        if not self.params:
            return self.code
        return f"{self.code} {self.params}"


class RouteError(AppError):
    """A route the app cannot use: not found, unparsable, or rejected by validate_route.

    Codes sit under route.*, and reach the user from the store's lookups, the editor's save
    payload and the engine's start path alike.
    """


class MapError(AppError):
    """A map that cannot be stored or matched against, under map.*.

    Covers an unreadable source image, a failed re-encode, and a missing reference.png -- the
    last of which also stops the engine from starting on an otherwise valid route.
    """


class ObjectsError(AppError):
    """An object set that failed validate_objects, under objects.*.

    Importing one surfaces it to the user; listing the sets of a map swallows it and skips the
    file, so one damaged set never hides the rest.
    """


class ShareCodeError(AppError):
    """Text offered as a share code that is not one, is damaged, or breaks the size caps.

    Codes sit under share.*. The caps are enforced on the encoded string and again while
    inflating, so a short code that expands without bound fails before anything is parsed.
    """


class VisionError(AppError):
    """A capture or matching failure the user has to act on, under vision.*.

    Fatal ones only: no reference to match against, or one nothing can be matched in. A
    transient miss is a warning notice and leaves the engine loop running.
    """


class SettingsError(AppError):
    """Settings and state failures, under settings.* and state.*.

    Loading deliberately does not raise it: a damaged file is backed up, replaced by defaults
    and reported through LoadResult, because a preferences file must never cost a start-up.
    """
