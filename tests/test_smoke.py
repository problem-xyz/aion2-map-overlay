"""The quickest end-to-end check: a route survives the trip through a share code."""

from map_overlay.store import routes, share


def test_share_code_round_trip() -> None:
    doc = {
        "format": routes.ROUTE_FORMAT,
        "version": routes.ROUTE_VERSION,
        "name": "Smoke",
        "mapSize": [100, 200],
        "markers": [{"x": 1.5, "y": 2.5, "text": "first"}],
    }

    decoded = share.decode_share(share.encode_share(doc))

    assert decoded == routes.validate_route(doc)
