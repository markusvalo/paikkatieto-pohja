"""Yhteiset testiaineistot. Kaikki testit toimivat ilman verkkoyhteyttä."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

# Helsingin päärautatieasema ja Oulun tori (lon, lat).
HELSINKI_LONLAT = (24.9414, 60.1719)
OULU_LONLAT = (25.4651, 65.0131)
BERLIINI_LONLAT = (13.4050, 52.5200)


@pytest.fixture
def helsinki_pisteet() -> gpd.GeoDataFrame:
    """Kolme pistettä Helsingissä, GK25FIN."""
    gdf = gpd.GeoDataFrame(
        {"nimi": ["Rautatieasema", "Töölönlahti", "Kallio"], "kerrosala_m2": [12000.5, 0.0, 850.25]},
        geometry=[Point(HELSINKI_LONLAT), Point(24.9370, 60.1760), Point(24.9500, 60.1840)],
        crs=4326,
    )
    return gdf.to_crs(3879)


@pytest.fixture
def tontti() -> gpd.GeoDataFrame:
    """U-muotoinen tontti (keskipiste osuu tontin ulkopuolelle), GK25FIN."""
    x0, y0 = 25_496_800.0, 6_673_000.0
    u = Polygon(
        [
            (x0, y0),
            (x0 + 30, y0),
            (x0 + 30, y0 + 30),
            (x0 + 20, y0 + 30),
            (x0 + 20, y0 + 10),
            (x0 + 10, y0 + 10),
            (x0 + 10, y0 + 30),
            (x0, y0 + 30),
        ]
    )
    return gpd.GeoDataFrame(
        {"kiinteistotunnus": ["091-004-0012-0003"], "osoite": ["Äyräpääntie 1 Å"]}, geometry=[u], crs=3879
    )
