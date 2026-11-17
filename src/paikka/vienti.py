"""Lopputuotteiden viennit.

| Muoto        | Käyttö                                         | CRS                    |
|--------------|------------------------------------------------|------------------------|
| GeoParquet   | Pääformaatti, analyysi, DuckDB, QGIS URL:sta    | analyysin CRS          |
| GeoPackage   | Toimitukset, QGIS, ArcGIS                      | analyysin CRS          |
| GeoJSON      | Verkko, tippecanoe → PMTiles                   | aina WGS84 (RFC 7946)  |
| Shapefile    | Vain jos vastaanottaja vaatii                  | analyysin CRS          |
| Power BI CSV | Power BI / Excel                               | WGS84 lat/lon-sarakkeet|
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import geopandas as gpd
import shapely

from paikka import crs as crs_mod
from paikka import merkisto

logger = logging.getLogger(__name__)

SHAPEFILE_KENTAN_PITUUS = 10
POWERBI_DESIMAALIT = 6  # ~0,1 m – riittää Power BI:n karttavisuaaleille
GEOJSON_DESIMAALIT = 7  # ~1 cm


def _valmistele(gdf: gpd.GeoDataFrame, polku: Path) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError("Vientiä ei tehdä ilman koordinaattijärjestelmää.")
    polku.parent.mkdir(parents=True, exist_ok=True)
    return merkisto.siivoa_tekstit(gdf, korjaa_mojibakea=False)


def vie_geoparquet(gdf: gpd.GeoDataFrame, polku: Path) -> Path:
    """GeoParquet (WKB, zstd-pakkaus, bbox-sarake nopeaa rajausta varten)."""
    gdf = _valmistele(gdf, polku)
    gdf.to_parquet(polku, index=False, compression="zstd", write_covering_bbox=True)
    return polku


def vie_geopackage(gdf: gpd.GeoDataFrame, polku: Path, taso: str | None = None) -> Path:
    """GeoPackage (UTF-8 määritelmän mukaan)."""
    gdf = _valmistele(gdf, polku)
    gdf.to_file(polku, layer=taso or polku.stem, driver="GPKG", engine="pyogrio")
    return polku


def vie_geojson(gdf: gpd.GeoDataFrame, polku: Path) -> Path:
    """GeoJSON RFC 7946: WGS84, lon/lat-järjestys, 7 desimaalia."""
    gdf = crs_mod.muunna(_valmistele(gdf, polku), crs_mod.WGS84)
    gdf.to_file(
        polku,
        driver="GeoJSON",
        engine="pyogrio",
        layer_options={"RFC7946": "YES", "COORDINATE_PRECISION": str(GEOJSON_DESIMAALIT), "WRITE_NAME": "NO"},
    )
    return polku


def shapefile_kentta(nimi: str) -> str:
    """Muunna sarakenimi Shapefile-yhteensopivaksi: ASCII, enintään 10 merkkiä.

    Esim. 'Kerrosala_m²' → 'kerrosala_', 'Rakennusvuosi' → 'rakennusvu', 'Pääkäyttö' → 'paakaytto'.
    """
    ascii_nimi = unicodedata.normalize("NFKD", nimi).encode("ascii", "ignore").decode("ascii")
    ascii_nimi = re.sub(r"[^A-Za-z0-9_]", "_", ascii_nimi).lower() or "kentta"
    return ascii_nimi[:SHAPEFILE_KENTAN_PITUUS]


def vie_shapefile(gdf: gpd.GeoDataFrame, polku: Path) -> dict[str, str]:
    """Shapefile UTF-8-koodauksella (.cpg) ja turvallisilla kenttänimillä.

    Returns:
        Kenttänimien muunnostaulukko {alkuperäinen: uusi}, joka kirjoitetaan myös
        tiedostoon ``<nimi>_kentat.csv`` vastaanottajaa varten.

    Raises:
        ValueError: Jos lyhennetyt kenttänimet törmäävät.
    """
    gdf = _valmistele(gdf, polku)
    nimet = {s: shapefile_kentta(s) for s in gdf.columns if s != gdf.geometry.name}
    if len(set(nimet.values())) != len(nimet):
        raise ValueError(f"Shapefile-kenttänimet törmäävät lyhennettyinä: {nimet}. Nimeä sarakkeet uudelleen.")
    gdf.rename(columns=nimet).to_file(polku, driver="ESRI Shapefile", engine="pyogrio", encoding="UTF-8")
    muunnos = gpd.pd.DataFrame({"alkuperainen": list(nimet), "shapefile": list(nimet.values())})
    merkisto.kirjoita_csv(muunnos, polku.with_name(f"{polku.stem}_kentat.csv"), murre="excel_fi")
    return nimet


def vie_powerbi(gdf: gpd.GeoDataFrame, polku: Path, wkt: bool = True) -> Path:
    """CSV Power BI:lle: WGS84 ``lat``/``lon``-sarakkeet ja valinnaisesti WKT-geometria.

    Pisteille lat/lon on piste itse. Viivoille ja alueille lat/lon on sisäpiste
    (``point_on_surface``) laskettuna alkuperäisessä metrisessä järjestelmässä – se on
    aina kohteen sisällä toisin kuin keskipiste (esim. U-muotoiset kiinteistöt).
    """
    gdf = _valmistele(gdf, polku)
    tulos = gdf.drop(columns=gdf.geometry.name).copy()
    pisteet = gpd.GeoSeries(shapely.point_on_surface(gdf.geometry.values), crs=gdf.crs).to_crs(4326)
    tulos["lat"] = pisteet.y.round(POWERBI_DESIMAALIT)
    tulos["lon"] = pisteet.x.round(POWERBI_DESIMAALIT)
    if wkt:
        tulos["wkt"] = shapely.to_wkt(gdf.to_crs(4326).geometry.values, rounding_precision=POWERBI_DESIMAALIT)
    merkisto.kirjoita_csv(tulos, polku, murre="powerbi")
    return polku


VIENNIT = {
    "geoparquet": vie_geoparquet,
    "gpkg": vie_geopackage,
    "geojson": vie_geojson,
    "shp": vie_shapefile,
    "powerbi": vie_powerbi,
}
