from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from paikka import crs, tarkistus


def _koodit(ongelmat: list[tarkistus.Ongelma]) -> set[str]:
    return {o.koodi for o in ongelmat}


def test_ehja_aineisto_lapaisee(helsinki_pisteet: gpd.GeoDataFrame, tontti: gpd.GeoDataFrame) -> None:
    assert tarkistus.tarkista(helsinki_pisteet) == []
    assert tarkistus.tarkista(tontti, pakolliset=["kiinteistotunnus"]) == []


def test_puuttuva_crs() -> None:
    gdf = gpd.GeoDataFrame(geometry=[Point(385_000, 6_672_000)])
    assert "crs_puuttuu" in _koodit(tarkistus.tarkista(gdf))


def test_kielletty_crs(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    kkj = helsinki_pisteet.to_crs(2392)  # KKJ / Finland zone 2
    assert "crs_ei_sallittu" in _koodit(tarkistus.tarkista(kkj))


def test_vaarat_akselit_annetaan_vihje(helsinki_pisteet: gpd.GeoDataFrame) -> None:
    ongelmat = tarkistus.tarkista(crs.vaihda_akselit(helsinki_pisteet))
    assert "kayttoalueen_ulkopuolella" in _koodit(ongelmat)
    assert any("väärin päin" in o.viesti for o in ongelmat)


def test_eurooppa_aineisto_suomi_tarkistuksessa() -> None:
    berliini = gpd.GeoDataFrame(geometry=[Point(13.405, 52.52)], crs=4326)
    assert "alueen_ulkopuolella" in _koodit(tarkistus.tarkista(berliini, alue="suomi"))
    assert tarkistus.tarkista(berliini, alue="eurooppa") == []


def test_virheellinen_geometria() -> None:
    rusetti = Polygon([(385_000, 6_672_000), (385_010, 6_672_010), (385_010, 6_672_000), (385_000, 6_672_010)])
    gdf = gpd.GeoDataFrame(geometry=[rusetti], crs=3067)
    assert "geometria_virheellinen" in _koodit(tarkistus.tarkista(gdf))


def test_pakollinen_sarake(tontti: gpd.GeoDataFrame) -> None:
    tontti.loc[0, "kiinteistotunnus"] = None
    assert "sarake_tyhja" in _koodit(tarkistus.tarkista(tontti, pakolliset=["kiinteistotunnus"]))
    assert "sarake_puuttuu" in _koodit(tarkistus.tarkista(tontti, pakolliset=["rakennustunnus"]))


def test_mojibake_on_virhe(tontti: gpd.GeoDataFrame) -> None:
    tontti["osoite"] = "Ã„yrÃ¤pÃ¤Ã¤ntie 1"
    with pytest.raises(tarkistus.TarkistusVirhe):
        tarkistus.varmista(tarkistus.tarkista(tontti))


def test_tyhja_aineisto() -> None:
    assert _koodit(tarkistus.tarkista(gpd.GeoDataFrame(geometry=[], crs=3067))) == {"tyhja"}
