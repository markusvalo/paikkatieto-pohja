"""Esimerkkiputki: haku → tarkistus → muunnos → lopputuotteet.

Hakee Helsingin rakennukset pieneltä alueelta (Kallio) GK25FIN:ssä ja tuottaa:
    data/products/aineisto.parquet   GeoParquet, GK25FIN (pääformaatti)
    data/products/aineisto.gpkg      GeoPackage, GK25FIN (toimitus, QGIS)
    data/products/aineisto.geojson   GeoJSON, WGS84 (→ PMTiles verkkokarttaan)
    data/products/aineisto_powerbi.csv  Power BI: lat/lon + WKT, UTF-8 BOM

Aja: ``pixi run esimerkki``. Vaatii verkkoyhteyden. Ajettu 21.11.2026 (277 rakennusta);
tarkista lähde tarvittaessa: ``pixi run paikka kokoelmat hki_rakennukset``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from paikka import crs, lahteet, tarkistus, vienti

JUURI = Path(__file__).resolve().parents[1]
TUOTTEET = JUURI / "data" / "products"
LAHDE_ID = "hki_rakennukset"
# Kallio, GK25FIN (minx, miny, maxx, maxy) – pidä esimerkkialue pienenä.
RAJAUS = (25_496_500.0, 6_673_500.0, 25_497_500.0, 6_674_500.0)

logger = logging.getLogger(__name__)


def aja() -> int:
    """Aja esimerkkiputki. Palauttaa prosessin paluukoodin."""
    rekisteri = lahteet.lataa_rekisteri(JUURI / "config" / "lahteet.yaml")
    lahde = rekisteri[LAHDE_ID]

    gdf = lahteet.hae(lahde, rajaus=RAJAUS, rajaus_epsg=crs.GK25.epsg)
    lahteet.tallenna_raaka(gdf, lahde, JUURI / "data" / "raw")

    ongelmat = tarkistus.tarkista(gdf, alue="suomi")
    tarkistus.varmista(ongelmat)

    # Analyysi tehdään GK25FIN:ssä (pääkaupunkiseutu, tonttitaso).
    gdf = crs.muunna(gdf, crs.GK25)
    gdf["pinta_ala_m2"] = gdf.geometry.area.round(1)

    tuote = crs.pyorista(gdf)
    vienti.vie_geoparquet(tuote, TUOTTEET / "aineisto.parquet")
    vienti.vie_geopackage(tuote, TUOTTEET / "aineisto.gpkg")
    vienti.vie_geojson(tuote, TUOTTEET / "aineisto.geojson")
    vienti.vie_powerbi(tuote, TUOTTEET / "aineisto_powerbi.csv")

    (TUOTTEET / "LAHTEET.txt").write_text(
        f"{lahde.nimi}\n{lahde.attribuutio}\nLisenssi: {lahde.lisenssi}\n", encoding="utf-8"
    )
    logger.info("Valmis: %d kohdetta → %s", len(tuote), TUOTTEET)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        sys.exit(aja())
    except tarkistus.TarkistusVirhe as e:
        logger.error("Aineisto ei läpäissyt tarkistusta:\n%s", e)
        sys.exit(1)
