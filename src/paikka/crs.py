"""Koordinaattijärjestelmäprofiilit ja muunnokset.

Käytäntö (ks. docs/adr/0001-koordinaattijarjestelmat.md):
    * GK25FIN (EPSG:3879) – Helsinki ja pääkaupunkiseutu, tontti- ja korttelitaso.
    * TM35FIN (EPSG:3067) – koko Suomi, kunta- ja maakuntataso, oletus.
    * ETRS-LAEA (EPSG:3035) – Eurooppa-tason analyysit (pinta-alat oikein).
    * WGS84 (EPSG:4326) – vain jakeluun: Power BI, GeoJSON, verkkokartat.

Akselijärjestys: EPSG määrittelee GK25FIN:n ja LAEA:n järjestykseen pohjoinen–itä ja
WGS84:n järjestykseen lat–lon. Tässä paketissa koordinaatit ovat AINA järjestyksessä
x=itä/lon, y=pohjoinen/lat (GeoPandas/Shapely-käytäntö). Rajapinnat (WFS 2.0, OGC API
Features crs-parametrilla) voivat palauttaa koordinaatit EPSG:n järjestyksessä, jolloin
x ja y ovat väärin päin. ``korjaa_akselit_tarvittaessa`` tunnistaa ja korjaa tämän.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cache

import geopandas as gpd
import shapely
from pyproj import CRS, Transformer

logger = logging.getLogger(__name__)

# Tarkkuudet: metriset 1 mm, maantieteelliset 1e-7 astetta (~1 cm).
METRINEN_TARKKUUS_M = 0.001
ASTE_TARKKUUS = 1e-7

# Toleranssi alueen rajoille (asteina), jotta rannikon ja rajan kohteet eivät hylkäänny.
ALUE_TOLERANSSI_ASTE = 0.05
# Toleranssi projektion käyttöalueen ulkopuolelle (metriä). GK-kaistoja käytetään käytännössä
# hieman kaistan yli (esim. kunnan reuna-alueet). Vaihtuneet akselit poikkeavat miljoonia metrejä,
# joten väljä toleranssi ei heikennä niiden tunnistusta.
KAYTTOALUE_TOLERANSSI_M = 20_000.0


@dataclass(frozen=True)
class CrsProfiili:
    """Projektissa käytettävä koordinaattijärjestelmä.

    Attributes:
        nimi: Lyhyt tunniste (käytetään komentorivillä).
        epsg: EPSG-koodi.
        kuvaus: Milloin profiilia käytetään.
        metrinen: True, jos yksikkö on metri.
    """

    nimi: str
    epsg: int
    kuvaus: str
    metrinen: bool

    @property
    def crs(self) -> CRS:
        """pyproj-CRS-olio."""
        return _crs(self.epsg)

    @property
    def tarkkuus(self) -> float:
        """Koordinaattien pyöristystarkkuus profiilin yksikössä."""
        return METRINEN_TARKKUUS_M if self.metrinen else ASTE_TARKKUUS


GK25 = CrsProfiili("gk25", 3879, "ETRS-GK25FIN – pääkaupunkiseutu, tonttitaso", metrinen=True)
TM35 = CrsProfiili("tm35", 3067, "ETRS-TM35FIN – koko Suomi (oletus)", metrinen=True)
LAEA = CrsProfiili("laea", 3035, "ETRS89-LAEA – Eurooppa-tason analyysit", metrinen=True)
WGS84 = CrsProfiili("wgs84", 4326, "WGS84 – jakelu (Power BI, GeoJSON, verkko)", metrinen=False)
WEB = CrsProfiili("web", 3857, "Web Mercator – vain verkkokarttojen tiilet", metrinen=True)

PROFIILIT: dict[str, CrsProfiili] = {p.nimi: p for p in (GK25, TM35, LAEA, WGS84, WEB)}
PROFIILIT_EPSG: dict[int, CrsProfiili] = {p.epsg: p for p in PROFIILIT.values()}

# Analyysialueet lon/lat-asteina (länsi, etelä, itä, pohjoinen).
SUOMI_LONLAT = (19.0, 58.8, 31.6, 70.1)
EUROOPPA_LONLAT = (-35.6, 24.6, 44.9, 84.8)
ALUEET: dict[str, tuple[float, float, float, float]] = {
    "suomi": SUOMI_LONLAT,
    "eurooppa": EUROOPPA_LONLAT,
}

type Rajat = tuple[float, float, float, float]


@cache
def _crs(epsg: int) -> CRS:
    return CRS.from_epsg(epsg)


@cache
def _muuntaja(lahde_epsg: int, kohde_epsg: int) -> Transformer:
    return Transformer.from_crs(_crs(lahde_epsg), _crs(kohde_epsg), always_xy=True)


def profiili(tunniste: str | int) -> CrsProfiili:
    """Palauta profiili nimen tai EPSG-koodin perusteella.

    Raises:
        KeyError: Jos profiilia ei ole määritelty.
    """
    if isinstance(tunniste, int) or str(tunniste).isdigit():
        epsg = int(tunniste)
        if epsg not in PROFIILIT_EPSG:
            raise KeyError(f"EPSG:{epsg} ei ole projektin profiili. Sallitut: {sorted(PROFIILIT_EPSG)}")
        return PROFIILIT_EPSG[epsg]
    nimi = str(tunniste).lower()
    if nimi not in PROFIILIT:
        raise KeyError(f"Tuntematon profiili '{tunniste}'. Sallitut: {sorted(PROFIILIT)}")
    return PROFIILIT[nimi]


def kayttoalue_lonlat(epsg: int) -> Rajat:
    """EPSG:n virallinen käyttöalue lon/lat-asteina."""
    alue = _crs(epsg).area_of_use
    if alue is None:
        raise ValueError(f"EPSG:{epsg} käyttöaluetta ei ole määritelty.")
    return alue.bounds


def lonlat_rajat_projektioon(rajat: Rajat, epsg: int) -> Rajat:
    """Muunna lon/lat-rajat annettuun järjestelmään (x=itä, y=pohjoinen)."""
    if epsg == 4326:
        return rajat
    return _muuntaja(4326, epsg).transform_bounds(*rajat, densify_pts=21)


def rajat_lonlat(gdf: gpd.GeoDataFrame) -> Rajat:
    """Aineiston rajat lon/lat-asteina."""
    _vaadi_crs(gdf)
    epsg = gdf.crs.to_epsg()
    rajat = tuple(gdf.total_bounds)
    if epsg == 4326:
        return rajat  # type: ignore[return-value]
    return _muuntaja(epsg, 4326).transform_bounds(*rajat, densify_pts=21)


def _sisalla(sisempi: Rajat, ulompi: Rajat, toleranssi: float = 0.0) -> bool:
    return (
        sisempi[0] >= ulompi[0] - toleranssi
        and sisempi[1] >= ulompi[1] - toleranssi
        and sisempi[2] <= ulompi[2] + toleranssi
        and sisempi[3] <= ulompi[3] + toleranssi
    )


def on_kayttoalueella(gdf: gpd.GeoDataFrame) -> bool:
    """Ovatko aineiston koordinaatit järjestelmänsä käyttöalueella.

    Tarkistus tehdään järjestelmän omissa yksiköissä, joten se paljastaa myös
    vaihtuneet akselit (esim. GK25FIN:n x≈6 670 000 eikä 25 497 000).
    """
    _vaadi_crs(gdf)
    epsg = gdf.crs.to_epsg()
    if epsg is None:
        raise ValueError("Aineiston CRS:llä ei ole EPSG-koodia.")
    alue = lonlat_rajat_projektioon(kayttoalue_lonlat(epsg), epsg)
    tol = KAYTTOALUE_TOLERANSSI_M if _crs(epsg).is_projected else ALUE_TOLERANSSI_ASTE
    return _sisalla(tuple(gdf.total_bounds), alue, tol)  # type: ignore[arg-type]


def vaihda_akselit(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Vaihda x- ja y-koordinaatit keskenään (palauttaa kopion)."""
    tulos = gdf.copy()
    tulos.geometry = shapely.transform(tulos.geometry.values, lambda xy: xy[:, ::-1])
    return tulos


def korjaa_akselit_tarvittaessa(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Korjaa vaihtuneet akselit, jos aineisto on käyttöalueella vain vaihdettuna.

    Returns:
        Alkuperäinen aineisto, jos se on kunnossa, muuten korjattu kopio.

    Raises:
        ValueError: Jos aineisto ei ole käyttöalueella kummassakaan järjestyksessä.
    """
    if gdf.empty or on_kayttoalueella(gdf):
        return gdf
    vaihdettu = vaihda_akselit(gdf)
    if on_kayttoalueella(vaihdettu):
        logger.warning(
            "Akselit olivat väärin päin (EPSG:%s) – korjattu järjestykseen x=itä, y=pohjoinen.",
            gdf.crs.to_epsg(),
        )
        return vaihdettu
    raise ValueError(
        f"Aineisto (rajat {tuple(round(v, 3) for v in gdf.total_bounds)}) ei ole EPSG:"
        f"{gdf.crs.to_epsg()}:n käyttöalueella. Onko CRS määritelty oikein?"
    )


def muunna(gdf: gpd.GeoDataFrame, kohde: str | int | CrsProfiili) -> gpd.GeoDataFrame:
    """Muunna aineisto toiseen järjestelmään ja tarkista tulos.

    Raises:
        ValueError: Jos lähtöaineistolla ei ole CRS:ää tai tulos on käyttöalueen ulkopuolella.
    """
    _vaadi_crs(gdf)
    kohdeprofiili = kohde if isinstance(kohde, CrsProfiili) else profiili(kohde)
    tulos = gdf.to_crs(kohdeprofiili.epsg)
    if not tulos.empty and not on_kayttoalueella(tulos):
        lonlat = rajat_lonlat(gdf)
        raise ValueError(
            f"Aineisto (lon/lat {tuple(round(v, 3) for v in lonlat)}) on {kohdeprofiili.nimi}-"
            f"järjestelmän käyttöalueen ulkopuolella. GK25FIN kattaa vain 24,5–25,5° itää; "
            f"käytä laajemmille alueille TM35FIN:ää (3067)."
        )
    return tulos


def pyorista(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Pyöristä koordinaatit profiilin tarkkuuteen (mm / ~1 cm). Palauttaa kopion.

    Pyöristys tehdään vasta lopputuotteisiin; analyysi tehdään täydellä tarkkuudella.
    """
    _vaadi_crs(gdf)
    epsg = gdf.crs.to_epsg()
    tarkkuus = PROFIILIT_EPSG[epsg].tarkkuus if epsg in PROFIILIT_EPSG else METRINEN_TARKKUUS_M
    tulos = gdf.copy()
    tulos.geometry = shapely.set_precision(tulos.geometry.values, tarkkuus)
    return tulos


def ehdota_crs(gdf: gpd.GeoDataFrame) -> CrsProfiili:
    """Ehdota analyysijärjestelmää aineiston laajuuden perusteella.

    GK25FIN, jos aineisto mahtuu sen kaistaan; TM35FIN, jos Suomessa; muuten LAEA.

    Raises:
        ValueError: Jos aineisto on Euroopan ulkopuolella.
    """
    lonlat = rajat_lonlat(gdf)
    if _sisalla(lonlat, kayttoalue_lonlat(GK25.epsg)):
        return GK25
    if _sisalla(lonlat, SUOMI_LONLAT, ALUE_TOLERANSSI_ASTE):
        return TM35
    if _sisalla(lonlat, EUROOPPA_LONLAT):
        return LAEA
    raise ValueError(f"Aineisto {lonlat} on Euroopan ulkopuolella – valitse järjestelmä erikseen.")


def _vaadi_crs(gdf: gpd.GeoDataFrame) -> None:
    if gdf.crs is None:
        raise ValueError("Aineistolta puuttuu koordinaattijärjestelmä (crs=None). Älä arvaa – selvitä lähteestä.")
