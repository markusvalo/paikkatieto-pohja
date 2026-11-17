"""Aineiston laatutarkistukset.

Käyttö putkessa::

    ongelmat = tarkista(gdf, alue="suomi", pakolliset=["kiinteistotunnus"])
    varmista(ongelmat)  # nostaa TarkistusVirhe-poikkeuksen, jos virheitä
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

import geopandas as gpd
import shapely

from paikka import crs as crs_mod
from paikka import merkisto

logger = logging.getLogger(__name__)

# Sallitut EPSG-koodit projektin aineistoissa (ks. ADR 0001).
SALLITUT_EPSG: frozenset[int] = frozenset({3879, 3067, 3035, 4326, 3857})

type Vakavuus = Literal["virhe", "varoitus"]


@dataclass(frozen=True)
class Ongelma:
    """Tarkistuksessa havaittu ongelma."""

    vakavuus: Vakavuus
    koodi: str
    viesti: str

    def __str__(self) -> str:
        return f"[{self.vakavuus.upper()}] {self.koodi}: {self.viesti}"


class TarkistusVirhe(Exception):
    """Aineisto ei läpäissyt tarkistusta."""

    def __init__(self, ongelmat: Sequence[Ongelma]) -> None:
        self.ongelmat = list(ongelmat)
        super().__init__("\n".join(str(o) for o in ongelmat))


def tarkista(
    gdf: gpd.GeoDataFrame,
    alue: Literal["suomi", "eurooppa"] | None = "suomi",
    pakolliset: Iterable[str] = (),
    sallitut_epsg: frozenset[int] = SALLITUT_EPSG,
) -> list[Ongelma]:
    """Aja kaikki tarkistukset ja palauta havaitut ongelmat.

    Args:
        gdf: Tarkistettava aineisto.
        alue: Alue, jolla aineiston on oltava (None = ei tarkistusta).
        pakolliset: Sarakkeet, joiden on oltava olemassa eikä niissä saa olla tyhjiä.
        sallitut_epsg: Hyväksytyt koordinaattijärjestelmät.
    """
    ongelmat: list[Ongelma] = []

    if gdf.empty:
        return [Ongelma("virhe", "tyhja", "Aineistossa ei ole kohteita.")]

    # --- Koordinaattijärjestelmä ---
    if gdf.crs is None:
        ongelmat.append(Ongelma("virhe", "crs_puuttuu", "Koordinaattijärjestelmä puuttuu."))
    else:
        epsg = gdf.crs.to_epsg()
        if epsg not in sallitut_epsg:
            ongelmat.append(
                Ongelma(
                    "virhe", "crs_ei_sallittu", f"EPSG:{epsg} ({gdf.crs.name}) ei ole sallittu: {sorted(sallitut_epsg)}"
                )
            )
        elif not crs_mod.on_kayttoalueella(gdf):
            vihje = (
                " Akselit ovat todennäköisesti väärin päin – käytä crs.korjaa_akselit_tarvittaessa()."
                if crs_mod.on_kayttoalueella(crs_mod.vaihda_akselit(gdf))
                else ""
            )
            ongelmat.append(
                Ongelma(
                    "virhe", "kayttoalueen_ulkopuolella", f"Koordinaatit eivät ole EPSG:{epsg}:n käyttöalueella.{vihje}"
                )
            )
        elif alue is not None:
            lonlat = crs_mod.rajat_lonlat(gdf)
            raja = crs_mod.ALUEET[alue]
            if not crs_mod._sisalla(lonlat, raja, crs_mod.ALUE_TOLERANSSI_ASTE):
                ongelmat.append(
                    Ongelma(
                        "virhe",
                        "alueen_ulkopuolella",
                        f"Aineisto {tuple(round(v, 3) for v in lonlat)} ei ole alueella '{alue}'.",
                    )
                )

    # --- Geometriat ---
    geom = gdf.geometry.values
    puuttuvat = int(shapely.is_missing(geom).sum())
    tyhjat = int(shapely.is_empty(geom).sum())
    virheelliset = int((~shapely.is_valid(geom) & ~shapely.is_missing(geom)).sum())
    if puuttuvat:
        ongelmat.append(Ongelma("virhe", "geometria_puuttuu", f"{puuttuvat} kohteelta puuttuu geometria."))
    if tyhjat:
        ongelmat.append(Ongelma("varoitus", "geometria_tyhja", f"{tyhjat} tyhjää geometriaa."))
    if virheelliset:
        syyt = shapely.is_valid_reason(geom[~shapely.is_valid(geom) & ~shapely.is_missing(geom)][:3])
        ongelmat.append(
            Ongelma(
                "virhe",
                "geometria_virheellinen",
                f"{virheelliset} virheellistä geometriaa, esim. {list(syyt)}. Korjaa: gdf.make_valid().",
            )
        )
    tyypit = set(gdf.geom_type.dropna().unique())
    if (
        len(tyypit) > 1
        and not tyypit <= {"Polygon", "MultiPolygon"}
        and not tyypit <= {"LineString", "MultiLineString"}
    ):
        ongelmat.append(
            Ongelma("varoitus", "sekalaiset_geometriatyypit", f"Useita geometriatyyppejä: {sorted(tyypit)}.")
        )

    # --- Sarakkeet ---
    for sarake in pakolliset:
        if sarake not in gdf.columns:
            ongelmat.append(Ongelma("virhe", "sarake_puuttuu", f"Pakollinen sarake '{sarake}' puuttuu."))
        elif (n := int(gdf[sarake].isna().sum())) > 0:
            ongelmat.append(Ongelma("virhe", "sarake_tyhja", f"Sarakkeessa '{sarake}' on {n} tyhjää arvoa."))

    # --- Tekstit ja merkistö ---
    for o in merkisto.tarkista_tekstit(gdf):
        vakavuus: Vakavuus = "virhe" if o.tyyppi == "mojibake" else "varoitus"
        ongelmat.append(Ongelma(vakavuus, f"teksti_{o.tyyppi}", f"{o.sarake}[{o.rivi}]: {o.arvo[:60]!r}"))

    return ongelmat


def varmista(ongelmat: Sequence[Ongelma]) -> None:
    """Kirjaa varoitukset lokiin ja nosta poikkeus, jos joukossa on virheitä.

    Raises:
        TarkistusVirhe: Jos yksikin ongelma on vakavuudeltaan 'virhe'.
    """
    for o in ongelmat:
        if o.vakavuus == "varoitus":
            logger.warning("%s", o)
    virheet = [o for o in ongelmat if o.vakavuus == "virhe"]
    if virheet:
        raise TarkistusVirhe(virheet)
