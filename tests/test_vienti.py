from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from paikka import vienti


def test_geoparquet_sailyttaa_crs_ja_aakkoset(tmp_path: Path, tontti: gpd.GeoDataFrame) -> None:
    polku = vienti.vie_geoparquet(tontti, tmp_path / "t.parquet")
    luettu = gpd.read_parquet(polku)
    assert luettu.crs.to_epsg() == 3879
    assert luettu["osoite"].iloc[0] == "Äyräpääntie 1 Å"


def test_geopackage(tmp_path: Path, helsinki_pisteet: gpd.GeoDataFrame) -> None:
    luettu = gpd.read_file(vienti.vie_geopackage(helsinki_pisteet, tmp_path / "p.gpkg"))
    assert luettu.crs.to_epsg() == 3879
    assert "Töölönlahti" in set(luettu["nimi"])


def test_geojson_on_wgs84_lonlat(tmp_path: Path, helsinki_pisteet: gpd.GeoDataFrame) -> None:
    polku = vienti.vie_geojson(helsinki_pisteet, tmp_path / "p.geojson")
    data = json.loads(polku.read_text(encoding="utf-8"))
    lon, lat = data["features"][0]["geometry"]["coordinates"]
    assert 24 < lon < 26 and 59 < lat < 61  # lon ensin (RFC 7946)
    assert "crs" not in data
    assert data["features"][0]["properties"]["nimi"] == "Rautatieasema"


def test_powerbi_csv_pisteet(tmp_path: Path, helsinki_pisteet: gpd.GeoDataFrame) -> None:
    df = pd.read_csv(vienti.vie_powerbi(helsinki_pisteet, tmp_path / "pbi.csv"), encoding="utf-8-sig")
    assert df["lat"].between(60, 61).all() and df["lon"].between(24, 26).all()
    assert df["wkt"].iloc[0].startswith("POINT (24.")
    assert "Töölönlahti" in set(df["nimi"])


def test_powerbi_alueen_piste_on_alueen_sisalla(tmp_path: Path, tontti: gpd.GeoDataFrame) -> None:
    df = pd.read_csv(vienti.vie_powerbi(tontti, tmp_path / "t.csv"), encoding="utf-8-sig")
    piste = gpd.GeoSeries([Point(df["lon"].iloc[0], df["lat"].iloc[0])], crs=4326).to_crs(3879).iloc[0]
    assert tontti.geometry.iloc[0].buffer(0.05).contains(piste)
    assert not tontti.geometry.iloc[0].contains(tontti.geometry.iloc[0].centroid)  # siksi point_on_surface


@pytest.mark.parametrize(
    ("nimi", "odotettu"),
    [("Pääkäyttö", "paakaytto"), ("Rakennusvuosi", "rakennusvu"), ("Kerrosala m²", "kerrosala_")],
)
def test_shapefile_kenttanimet(nimi: str, odotettu: str) -> None:
    assert vienti.shapefile_kentta(nimi) == odotettu


def test_shapefile_utf8_ja_muunnostaulukko(tmp_path: Path, tontti: gpd.GeoDataFrame) -> None:
    polku = tmp_path / "tontit.shp"
    nimet = vienti.vie_shapefile(tontti, polku)
    assert polku.with_suffix(".cpg").read_text(encoding="ascii").strip().upper() in {"UTF-8", "UTF8"}
    luettu = gpd.read_file(polku)
    assert luettu[nimet["osoite"]].iloc[0] == "Äyräpääntie 1 Å"
    assert (tmp_path / "tontit_kentat.csv").exists()


def test_shapefile_tormaavat_nimet(tmp_path: Path, tontti: gpd.GeoDataFrame) -> None:
    tontti["rakennusvuosi_1"] = 1
    tontti["rakennusvuosi_2"] = 2
    with pytest.raises(ValueError, match="törmäävät"):
        vienti.vie_shapefile(tontti, tmp_path / "x.shp")
