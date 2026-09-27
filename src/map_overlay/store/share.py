"""Route share codes: one route as a single pasteable string.

A share code arrives from the clipboard, which means it arrives from anywhere. It is
compressed, so a few kilobytes of input can expand into gigabytes if decompressed without a
limit -- the classic zip bomb. Both ends are therefore capped: the encoded text before it is
decoded, and the decompressed bytes as they come out.
"""

import base64
import json
import re
import zlib
from typing import Any

from map_overlay.core.errors import ShareCodeError
from map_overlay.store.routes import validate_route

SHARE_PREFIX = "MO1."

# A 2000-point route encodes to well under 20 KB, so this is generous.
MAX_ENCODED_BYTES = 64_000
MAX_DECODED_BYTES = 1_000_000


def encode_share(doc: Any) -> str:
    """A route on one line: MO1. + zlib + base64url.

    Fifty points measures at roughly 800 characters bare and about 1 KB once the steps carry
    text, so it pastes into a chat message but not into a title field. Coordinates dominate:
    they are stored to two decimals, and those digits do not compress.
    """
    raw = json.dumps(validate_route(doc), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    packed = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
    return SHARE_PREFIX + packed


def _inflate(data: bytes) -> bytes:
    """Decompress with a ceiling, so a small code cannot expand without bound."""
    obj = zlib.decompressobj()
    raw = obj.decompress(data, max_length=MAX_DECODED_BYTES)
    if obj.unconsumed_tail:
        raise ShareCodeError("share.too_large", limit=MAX_DECODED_BYTES)
    return raw


def decode_share(text: Any) -> dict[str, Any]:
    text = re.sub(r"\s+", "", str(text or ""))
    if not text.startswith(SHARE_PREFIX):
        raise ShareCodeError("share.not_a_code")

    body = text[len(SHARE_PREFIX) :]
    if len(body) > MAX_ENCODED_BYTES:
        raise ShareCodeError("share.too_large", limit=MAX_ENCODED_BYTES)

    body += "=" * (-len(body) % 4)
    try:
        raw = _inflate(base64.urlsafe_b64decode(body))
        doc = json.loads(raw.decode("utf-8"))
    except ShareCodeError:
        raise
    except Exception as e:
        raise ShareCodeError("share.corrupt") from e
    return validate_route(doc)
