from __future__ import annotations

import h3

DEFAULT_H3_RESOLUTION = 9


def latlng_to_h3(latitude: float, longitude: float, resolution: int = DEFAULT_H3_RESOLUTION) -> str:
    """Return the H3 index for the given lat/lng pair."""
    return h3.latlng_to_cell(latitude, longitude, resolution)
