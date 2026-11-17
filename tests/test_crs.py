from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from paikka import crs
from tests.conftest import BERLIINI_LONLAT, OULU_LONLAT


def _piste(lonlat: tuple[float, float]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(geometry=[Point(lonlat)], crs=4326)


def test_gk25_koordinaatit_oikeassa_suuruusluokassa(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    x, y = helsinki_pisteet.geometry.iloc[0].coords[0]
    assert 25_490_000 < x < 25_500_000  # itä: kaistatunnus 25 + 500 000
    assert 6_670_000 < y < 6_676_000
    assert crs.on_kayttoalueella(helsinki_pisteet)


def test_tm35_muunnos(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    tm = crs.muunna(helsinki_pisteet, "tm35")
    x, y = tm.geometry.iloc[0].coords[0]
    assert tm.crs.to_epsg() == 3067
    assert x == pytest.approx(385_800, abs=1_000)
    assert y == pytest.approx(6_672_000, abs=1_000)


def test_edestakainen_muunnos_millin_tarkkuudella(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    takaisin = crs.muunna(crs.muunna(helsinki_pisteet, 3067), 3879)
    erot = helsinki_pisteet.geometry.distance(takaisin.geometry)
    assert erot.max() < 0.001


def test_vaihtuneet_akselit_tunnistetaan_ja_korjataan(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    vaarin = crs.vaihda_akselit(helsinki_pisteet)  # kuten WFS 2.0 / EPSG-järjestys N,E
    assert not crs.on_kayttoalueella(vaarin)
    korjattu = crs.korjaa_akselit_tarvittaessa(vaarin)
    assert korjattu.geometry.distance(helsinki_pisteet.geometry).max() == 0


def test_oikeita_akseleita_ei_kosketa(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    assert crs.korjaa_akselit_tarvittaessa(helsinki_pisteet) is helsinki_pisteet


def test_gk25_kaistan_ulkopuolelle_ei_muunneta() -> None:
    with pytest.raises(ValueError, match="GK25FIN kattaa"):
        crs.muunna(
            _piste(OULU_LONLAT).to_crs(3067).pipe(lambda g: g.set_geometry(g.geometry.translate(150_000))), "gk25"
        )


@pytest.mark.parametrize(
    ("lonlat", "odotettu"),
    [((24.9414, 60.1719), 3879), (OULU_LONLAT, 3879), ((27.68, 62.89), 3067), (BERLIINI_LONLAT, 3035)],
)
def test_ehdota_crs(lonlat: tuple[float, float], odotettu: int) -> None:
    # Oulu on GK25-kaistalla (25,47° E) – ehdotus on silti oikea, kaista ratkaisee.
    assert crs.ehdota_crs(_piste(lonlat)).epsg == odotettu


def test_puuttuva_crs_on_virhe() -> None:
    with pytest.raises(ValueError, match="crs=None"):
        crs.muunna(gpd.GeoDataFrame(geometry=[Point(0, 0)]), "tm35")


def test_pyoristys_millimetriin(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    x, _ = crs.pyorista(helsinki_pisteet).geometry.iloc[0].coords[0]
    assert round(x, 3) == x


def test_tuntematon_profiili() -> None:
    with pytest.raises(KeyError):
        crs.profiili(2393)  # KKJ3 – muunnettava ennen käyttöä
