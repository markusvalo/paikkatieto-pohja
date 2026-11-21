"""Lähderekisteri ja aineistohaut.

Lähteet kuvataan tiedostossa ``config/lahteet.yaml``. Jokaisella lähteellä on lisenssi ja
attribuutio, jotka kulkevat raakadatan metatiedoissa lopputuotteisiin asti.

Haettavat tyypit: OGC API Features, WFS 2.0 (sivutus) ja WFS 1.0 / GML2 (``wfs_gml``) sekä tiedostot.
``mcp`` (paikka.mcp) ja ``wms`` (vain QGIS) kirjataan rekisteriin, mutta ``hae()`` torjuu ne.
Palvelun kuvaus: ``hae_capabilities()``, ``tasonimet()``, ``kuvaa_kokoelma()``; vaihtuvat tasonimet
paikkamerkeillä (``{vuosi}``, ``{jakso}``) ja ``taydenna()``.

API-avaimet luetaan ympäristömuuttujista (GitHubissa: Settings → Secrets). Niitä ei
koskaan kirjoiteta lokiin, metatietoihin eikä repoon.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import geopandas as gpd
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from paikka import crs as crs_mod
from paikka import merkisto

logger = logging.getLogger(__name__)

AIKAKATKAISU_S = 60
SIVUKOKO = 1000
MAKSIMI_SIVUT = 1000  # Suojaa loputtomalta sivutukselta (1 000 × 1 000 = 1 milj. kohdetta).
YRITYKSET = 4

# wfs_gml: WFS 1.0.0 ja GML2 yhdellä pyynnöllä ilman sivutusta (palvelut, jotka eivät tarjoa GeoJSONia).
# mcp: sijainniton MCP-palvelu (esim. arkistojen hakupalvelut), käytetään MCP-asiakkaalla, ei hae()-funktiolla.
# wms: karttakuvapalvelu, jota vain QGIS lukee; putket eivät hae siitä dataa. Kirjataan rekisteriin lisenssin vuoksi.
type LahdeTyyppi = Literal["ogc_api_features", "wfs", "wfs_gml", "tiedosto", "mcp", "wms"]
SIJAINNITTOMAT: frozenset[str] = frozenset({"mcp"})  # tyypit, joilla ei ole koordinaattijärjestelmää
type Rajaus = tuple[float, float, float, float]


@dataclass(frozen=True)
class Lahde:
    """Yksi aineistolähde lähderekisterissä."""

    id: str
    nimi: str
    tyyppi: LahdeTyyppi
    url: str
    lisenssi: str
    attribuutio: str
    epsg: int | None = None  # pakollinen paikkatietolähteille; sijainnittomilla (mcp) ei ole
    paivitys: str = "tuntematon"
    kokoelma: str | None = None  # OGC API Features -kokoelma tai WFS-tason nimi
    api_avain_env: str | None = None
    api_avain_parametri: str = "api-key"
    huom: str = ""
    lisaparametrit: dict[str, str] = field(default_factory=dict)


class _Istunto(Protocol):
    def get(self, url: str, params: dict[str, Any] | None = ..., timeout: float = ...) -> requests.Response: ...


def lataa_rekisteri(polku: Path) -> dict[str, Lahde]:
    """Lue lähderekisteri YAML-tiedostosta.

    Raises:
        ValueError: Jos lähteen kuvauksesta puuttuu pakollisia kenttiä.
    """
    with polku.open(encoding="utf-8") as f:
        raaka = yaml.safe_load(f) or {}
    lahteet: dict[str, Lahde] = {}
    for tunnus, kuvaus in (raaka.get("lahteet") or {}).items():
        try:
            lahteet[tunnus] = Lahde(id=tunnus, **kuvaus)
        except TypeError as e:
            raise ValueError(f"Lähteen '{tunnus}' kuvaus on virheellinen: {e}") from e
        if lahteet[tunnus].epsg is None and lahteet[tunnus].tyyppi not in SIJAINNITTOMAT:
            # CLAUDE.md, sääntö 1: paikkatietolähteen koordinaattijärjestelmä on aina tiedossa.
            raise ValueError(f"Lähteeltä '{tunnus}' puuttuu epsg (pakollinen paikkatietolähteille).")
    return lahteet


def luo_istunto() -> requests.Session:
    """HTTP-istunto uudelleenyrityksillä (429/5xx, eksponentiaalinen odotus)."""
    istunto = requests.Session()
    uudelleen = Retry(
        total=YRITYKSET, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",)
    )
    istunto.mount("https://", HTTPAdapter(max_retries=uudelleen))
    istunto.headers["User-Agent"] = "paikkatieto-pohja/0.1 (+https://github.com)"
    return istunto


def peita_avaimet(url: str) -> str:
    """Poista kyselyparametrit URL:sta lokia ja metatietoja varten."""
    osat = urlsplit(url)
    return urlunsplit((osat.scheme, osat.netloc, osat.path, "", ""))


def _api_avain(lahde: Lahde) -> dict[str, str]:
    if not lahde.api_avain_env:
        return {}
    # strip(): salaisuuteen jää helposti rivinvaihto tai välilyönti liitettäessä.
    avain = (os.environ.get(lahde.api_avain_env) or "").strip()
    if not avain:
        raise RuntimeError(f"Lähde '{lahde.id}' vaatii API-avaimen ympäristömuuttujassa {lahde.api_avain_env}.")
    return {lahde.api_avain_parametri: avain}


def _tarkista_vastaus(vastaus: requests.Response) -> None:
    """Nosta virhe ilman API-avainta: requestsin oma virheilmoitus sisältää koko URL:n.

    Raises:
        RuntimeError: Jos vastaus on virhe (4xx/5xx). Viestissä on palvelimen selitys (esim. OWS
            ExceptionReport tai JSON), jotta syy näkyy ilman uutta pyyntöä.
    """
    try:
        vastaus.raise_for_status()
    except requests.HTTPError:
        selitys = (getattr(vastaus, "text", "") or "").strip().replace("\n", " ")[:300]
        vinkki = {
            400: " Tarkista parametrit (GeoServerin sivutus vaatii sortBy-lajittelun, jos tasolla ei ole pääavainta).",
            401: " Tarkista API-avain.",
            403: " API-avain puuttuu, on virheellinen tai sillä ei ole oikeutta palveluun.",
            429: " Liikaa kyselyitä – yritä myöhemmin.",
        }.get(vastaus.status_code, "")
        raise RuntimeError(
            f"HTTP {vastaus.status_code} {peita_avaimet(vastaus.url)}.{vinkki} Palvelin: {selitys or '(ei selitystä)'}"
        ) from None


def _crs_uri(epsg: int) -> str:
    return f"http://www.opengis.net/def/crs/EPSG/0/{epsg}"


def _ogc_sivut(lahde: Lahde, istunto: _Istunto, rajaus: Rajaus | None, rajaus_epsg: int | None) -> Iterator[list[dict]]:
    url = f"{lahde.url.rstrip('/')}/collections/{lahde.kokoelma}/items"
    parametrit: dict[str, Any] = {
        "f": "json",
        "limit": SIVUKOKO,
        "crs": _crs_uri(lahde.epsg),
        **lahde.lisaparametrit,
        **_api_avain(lahde),
    }
    if rajaus:
        parametrit["bbox"] = ",".join(str(v) for v in rajaus)
        parametrit["bbox-crs"] = _crs_uri(rajaus_epsg or lahde.epsg)
    for _ in range(MAKSIMI_SIVUT):
        vastaus = istunto.get(url, params=parametrit, timeout=AIKAKATKAISU_S)
        _tarkista_vastaus(vastaus)
        sisalto = vastaus.json()
        yield sisalto.get("features", [])
        seuraava = next((linkki["href"] for linkki in sisalto.get("links", []) if linkki.get("rel") == "next"), None)
        if not seuraava:
            return
        # next-linkki sisältää jo parametrit (paitsi joskus API-avaimen).
        url, parametrit = seuraava, _api_avain(lahde)
    raise RuntimeError(f"Sivutus ylitti {MAKSIMI_SIVUT} sivua lähteessä {lahde.id}.")


def _wfs_sivut(lahde: Lahde, istunto: _Istunto, rajaus: Rajaus | None, rajaus_epsg: int | None) -> Iterator[list[dict]]:
    for sivu in range(MAKSIMI_SIVUT):
        parametrit: dict[str, Any] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": lahde.kokoelma,
            "outputFormat": "application/json",
            "srsName": f"EPSG:{lahde.epsg}",
            "count": SIVUKOKO,
            "startIndex": sivu * SIVUKOKO,
            **lahde.lisaparametrit,
            **_api_avain(lahde),
        }
        if rajaus:
            parametrit["bbox"] = ",".join(str(v) for v in rajaus) + f",EPSG:{rajaus_epsg or lahde.epsg}"
        vastaus = istunto.get(lahde.url, params=parametrit, timeout=AIKAKATKAISU_S)
        _tarkista_vastaus(vastaus)
        kohteet = vastaus.json().get("features", [])
        yield kohteet
        if len(kohteet) < SIVUKOKO:
            return
    raise RuntimeError(f"Sivutus ylitti {MAKSIMI_SIVUT} sivua lähteessä {lahde.id}.")


# GML:n srsName-muodot, joista EPSG-koodi tunnistetaan: "EPSG:3879", ".../epsg.xml#3879",
# "urn:ogc:def:crs:EPSG::3879" ja "http://www.opengis.net/def/crs/EPSG/0/3879".
_SRSNAME = re.compile(rb'srsName="([^"]*?(?:EPSG:|epsg\.xml#|EPSG::|/EPSG/0/)(\d+))"')
_SCHEMALOCATION = re.compile(rb'\sxsi:schemaLocation="[^"]*"')


def _wfs_gml(lahde: Lahde, istunto: _Istunto, rajaus: Rajaus | None, rajaus_epsg: int | None) -> gpd.GeoDataFrame:
    """Hae WFS 1.0.0 -taso GML2-muodossa yhdellä pyynnöllä.

    srsName-arvot muutetaan muotoon ``EPSG:<koodi>``, jotta GDAL ei yritä hakea määritelmää verkosta,
    ja XSD-viittaus poistetaan, jotta kenttätyypit päätellään aina samalla tavalla aineistosta.
    Koordinaattijärjestelmän on oltava sama kuin rekisterissä, muuten haku keskeytetään (ei arvausta).
    WFS 1.0:ssa akselijärjestys on aina x=itä, y=pohjoinen.

    Raises:
        ValueError: Jos vastauksen srsName on eri järjestelmässä kuin rekisterissä tai rajaus on eri järjestelmässä.
        RuntimeError: Jos palvelu palauttaa virheen (ServiceException).
    """
    parametrit: dict[str, Any] = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": lahde.kokoelma,
        "srsName": f"EPSG:{lahde.epsg}",
        "outputFormat": "GML2",
        **lahde.lisaparametrit,
        **_api_avain(lahde),
    }
    if rajaus:
        if (rajaus_epsg or lahde.epsg) != lahde.epsg:
            raise ValueError(f"WFS 1.0 -rajauksen on oltava lähteen järjestelmässä EPSG:{lahde.epsg}.")
        parametrit["bbox"] = ",".join(str(v) for v in rajaus)
    vastaus = istunto.get(lahde.url, params=parametrit, timeout=AIKAKATKAISU_S)
    _tarkista_vastaus(vastaus)
    data = vastaus.content
    if b"ServiceException" in data[:4000]:
        selitys = data[:4000].decode("utf-8", errors="replace").strip().replace("\n", " ")[:300]
        raise RuntimeError(f"Lähde {lahde.id}: WFS-palvelu palautti virheen: {selitys}")
    koodit = {int(k) for _, k in _SRSNAME.findall(data)}
    if koodit - {lahde.epsg}:
        raise ValueError(
            f"Lähde {lahde.id}: vastaus on järjestelmässä {sorted(koodit)}, rekisterissä EPSG:{lahde.epsg}."
        )
    data = _SRSNAME.sub(f'srsName="EPSG:{lahde.epsg}"'.encode(), data)
    data = _SCHEMALOCATION.sub(b"", data, count=1)
    if b"featureMember" not in data:
        return gpd.GeoDataFrame(geometry=[], crs=lahde.epsg)
    gdf = gpd.read_file(io.BytesIO(data))
    if "gml_id" in gdf.columns and gdf["gml_id"].isna().all():
        gdf = gdf.drop(columns="gml_id")
    # CRS on tarkistettu yllä srsName-arvoista; rekisterin arvo vastaa palvelun ilmoittamaa.
    return gdf.set_crs(lahde.epsg, allow_override=True)


# --- Palvelun kuvaus ja vaihtuvat tasonimet -------------------------------------------------

# Puolivuotisjakson merkinnät tasonimissä: "12026" (I/2026), "22025" (II/2025), "I_2024", "II_2024"
# ja päivämäärä "20170811" (tammi–kesäkuu = I, heinä–joulukuu = II).
_JAKSO = re.compile(r"^(?:([12])(\d{4})|(I{1,2})_(\d{4})|(\d{4})(\d{2})(\d{2}))$")


def hae_capabilities(lahde: Lahde, istunto: _Istunto | None = None, versio: str = "2.0.0") -> str:
    """WFS-palvelun GetCapabilities-vastaus tekstinä.

    Raises:
        ValueError: Jos lähde ei ole WFS-lähde.
        RuntimeError: Jos palvelu palauttaa virheen.
    """
    if lahde.tyyppi not in ("wfs", "wfs_gml"):
        raise ValueError(f"Lähde {lahde.id} ei ole WFS-lähde.")
    istunto = istunto or luo_istunto()
    parametrit = {"service": "WFS", "version": versio, "request": "GetCapabilities", **_api_avain(lahde)}
    vastaus = istunto.get(lahde.url, params=parametrit, timeout=AIKAKATKAISU_S)
    _tarkista_vastaus(vastaus)
    return vastaus.text


def tasonimet(capabilities: str) -> list[str]:
    """Palvelun tasojen nimet (FeatureType/Name) GetCapabilities-vastauksesta, nimiavaruudesta riippumatta.

    Raises:
        ValueError: Jos vastaus ei ole XML:ää.
    """
    try:
        juuri = ElementTree.fromstring(capabilities.encode("utf-8"))
    except ElementTree.ParseError as e:
        raise ValueError(f"GetCapabilities-vastaus ei ole XML:ää: {e}") from e
    nimet = []
    for elementti in juuri.iter():
        if elementti.tag.rsplit("}", 1)[-1] == "FeatureType":
            nimi = next((c.text for c in elementti if c.tag.rsplit("}", 1)[-1] == "Name" and c.text), None)
            if nimi:
                nimet.append(nimi.strip())
    return nimet


def paikkamerkin_arvot(nimet: list[str], kokoelma: str, paikkamerkki: str) -> list[str]:
    """Arvot, joilla kokoelman paikkamerkki (esim. ``{vuosi}``) tuottaa palvelun tasonimen.

    Esimerkki: kokoelma ``ns:Ruudukko_{vuosi}`` ja nimet ``ns:Ruudukko_2023``, ``ns:Ruudukko_2024`` →
    ``["2023", "2024"]``.

    Raises:
        ValueError: Jos kokoelmassa ei ole paikkamerkkiä tai siinä on muita paikkamerkkejä.
    """
    merkki = "{" + paikkamerkki + "}"
    if merkki not in kokoelma:
        raise ValueError(f"Kokoelmassa {kokoelma} ei ole paikkamerkkiä {merkki}.")
    alku, _, loppu = kokoelma.partition(merkki)
    if "{" in alku + loppu:
        raise ValueError(f"Kokoelmassa {kokoelma} on muita paikkamerkkejä kuin {merkki}.")
    malli = re.compile(f"^{re.escape(alku)}(.+?){re.escape(loppu)}$")
    return [m.group(1) for n in nimet if (m := malli.match(n))]


def vuodet(nimet: list[str], kokoelma: str) -> list[int]:
    """Kokoelman ``{vuosi}``-paikkamerkin vuodet palvelussa nousevassa järjestyksessä.

    Raises:
        ValueError: Jos palvelussa ei ole yhtään vuotta.
    """
    loydetyt = sorted({int(a) for a in paikkamerkin_arvot(nimet, kokoelma, "vuosi") if re.fullmatch(r"\d{4}", a)})
    if not loydetyt:
        raise ValueError(f"Palvelussa ei ole tasoa {kokoelma}.")
    return loydetyt


def jakso(tunniste: str) -> tuple[int, int] | None:
    """Puolivuotisjakso (vuosi, 1 | 2) tasonimen osasta: ``12026`` → (2026, 1), ``I_2024`` → (2024, 1),
    ``20170811`` → (2017, 2). Tuntematon muoto → None."""
    m = _JAKSO.match(tunniste)
    if not m:
        return None
    if m.group(1):
        return int(m.group(2)), int(m.group(1))
    if m.group(3):
        return int(m.group(4)), len(m.group(3))
    return int(m.group(5)), 1 if int(m.group(6)) <= 6 else 2


def uusin_jakso(nimet: list[str], kokoelma: str) -> tuple[str, tuple[int, int]]:
    """Kokoelman ``{jakso}``-paikkamerkin uusin arvo ja sen jakso.

    Raises:
        ValueError: Jos palvelussa ei ole yhtään tunnistettavaa jaksoa.
    """
    ehdokkaat = [(j, a) for a in paikkamerkin_arvot(nimet, kokoelma, "jakso") if (j := jakso(a))]
    if not ehdokkaat:
        raise ValueError(f"Palvelussa ei ole tasoa {kokoelma}.")
    j, arvo = max(ehdokkaat)
    return arvo, j


def taydenna(lahde: Lahde, **arvot: object) -> Lahde:
    """Lähde, jonka kokoelman paikkamerkit (esim. ``{vuosi}``) on korvattu annetuilla arvoilla.

    Raises:
        ValueError: Jos kokoelmaan jää paikkamerkki ilman arvoa.
    """
    if not lahde.kokoelma:
        return lahde
    try:
        kokoelma = lahde.kokoelma.format(**arvot)
    except KeyError as e:
        raise ValueError(f"Lähteen {lahde.id} kokoelman paikkamerkille {e} ei annettu arvoa.") from e
    return replace(lahde, kokoelma=kokoelma)


def kuvaa_kokoelma(lahde: Lahde, istunto: _Istunto | None = None) -> dict[str, Any]:
    """Tarkista OGC API Features -kokoelma: tuetut CRS:t ja esimerkkikohteen kentät.

    Käytetään ennen uuden putken kirjoittamista varmistamaan, että rekisterin kokoelmanimi,
    koordinaattijärjestelmä ja kenttänimet vastaavat rajapintaa.

    Returns:
        {"kokoelma", "otsikko", "crs": [...], "tukee_epsg": bool, "kentat": {nimi: esimerkkiarvo}}

    Raises:
        ValueError: Jos lähde ei ole OGC API Features -lähde.
    """
    if lahde.tyyppi != "ogc_api_features":
        raise ValueError(f"Lähde {lahde.id} ei ole OGC API Features -lähde.")
    istunto = istunto or luo_istunto()
    perus = f"{lahde.url.rstrip('/')}/collections/{lahde.kokoelma}"
    vastaus = istunto.get(perus, params={"f": "json", **_api_avain(lahde)}, timeout=AIKAKATKAISU_S)
    _tarkista_vastaus(vastaus)
    kuvaus = vastaus.json()
    crs_lista = [str(c) for c in kuvaus.get("crs", [])]
    kohteet = istunto.get(
        f"{perus}/items", params={"f": "json", "limit": 1, **_api_avain(lahde)}, timeout=AIKAKATKAISU_S
    )
    _tarkista_vastaus(kohteet)
    ensimmainen = next(iter(kohteet.json().get("features", [])), {})
    return {
        "kokoelma": lahde.kokoelma,
        "otsikko": kuvaus.get("title", ""),
        "crs": crs_lista,
        "tukee_epsg": any(c.rstrip("/").endswith(f"/{lahde.epsg}") for c in crs_lista),
        "kentat": dict(ensimmainen.get("properties") or {}),
    }


def hae(
    lahde: Lahde,
    rajaus: Rajaus | None = None,
    rajaus_epsg: int | None = None,
    istunto: _Istunto | None = None,
) -> gpd.GeoDataFrame:
    """Hae lähteen aineisto GeoDataFrameksi.

    Koordinaatit palautetaan lähteen järjestelmässä (``lahde.epsg``), akselijärjestys
    tarkistettuna ja tekstit NFC-normalisoituna.

    Args:
        lahde: Lähderekisterin lähde.
        rajaus: Valinnainen rajaus (minx, miny, maxx, maxy) järjestyksessä x=itä, y=pohjoinen.
        rajaus_epsg: Rajauksen järjestelmä (oletus: lähteen järjestelmä).
        istunto: HTTP-istunto (testeissä korvattavissa).

    GeoJSON-kohteen tunniste (``id``) säilytetään kenttänä ``kohde_id``, jotta yksittäisen kohteen voi
    jäljittää lähteeseen.

    Raises:
        ValueError: Jos lähde ei ole haettava paikkatietolähde (``mcp``, ``wms``).
        RuntimeError: Jos palvelu palauttaa virheen.
    """
    if lahde.tyyppi in SIJAINNITTOMAT or lahde.epsg is None:
        raise ValueError(f"Lähde '{lahde.id}' ei ole paikkatietolähde – käytä MCP-asiakasta (paikka.mcp).")
    if lahde.tyyppi == "wms":
        raise ValueError(
            f"Lähde '{lahde.id}' on karttakuvapalvelu (WMS), josta ei haeta kohteita – vain QGIS lukee sen."
        )
    if lahde.kokoelma and re.search(r"\{\w+\}", lahde.kokoelma):
        raise ValueError(
            f"Lähteen {lahde.id} kokoelmassa on paikkamerkki ({lahde.kokoelma}). Täydennä se: lahteet.taydenna()."
        )
    istunto = istunto or luo_istunto()
    logger.info("Haetaan %s (%s) – %s", lahde.id, lahde.tyyppi, peita_avaimet(lahde.url))

    if lahde.tyyppi == "tiedosto":
        polku = lahde.url if not lahde.url.startswith("http") else f"/vsicurl/{lahde.url}"
        gdf = gpd.read_file(polku, layer=lahde.kokoelma, bbox=rajaus)
        if gdf.crs is None:
            logger.warning("Tiedostossa ei ole CRS:ää – käytetään rekisterin arvoa EPSG:%s.", lahde.epsg)
            gdf = gdf.set_crs(lahde.epsg)
    elif lahde.tyyppi == "wfs_gml":
        gdf = _wfs_gml(lahde, istunto, rajaus, rajaus_epsg)
    else:
        sivuttaja = _ogc_sivut if lahde.tyyppi == "ogc_api_features" else _wfs_sivut
        kohteet = [k for sivu in sivuttaja(lahde, istunto, rajaus, rajaus_epsg) for k in sivu]
        for kohde in kohteet:
            if "id" in kohde:
                kohde["properties"] = kohde.get("properties") or {}
                kohde["properties"].setdefault("kohde_id", kohde["id"])
        gdf = (
            gpd.GeoDataFrame.from_features(kohteet, crs=lahde.epsg)
            if kohteet
            else gpd.GeoDataFrame(geometry=[], crs=lahde.epsg)
        )

    gdf = crs_mod.korjaa_akselit_tarvittaessa(gdf)
    gdf = merkisto.siivoa_tekstit(gdf, korjaa_mojibakea=False)  # Mojibake raportoidaan, ei korjata hiljaa.
    logger.info("Haettu %d kohdetta lähteestä %s.", len(gdf), lahde.id)
    return gdf


def tallenna_raaka(gdf: gpd.GeoDataFrame, lahde: Lahde, juuri: Path) -> Path | None:
    """Tallenna raakadata ja metatiedot hakemistoon ``juuri/<lähde>/``.

    Tallennus ohitetaan, jos sisältö ei ole muuttunut edellisestä hausta (SHA-256).

    Returns:
        Tallennetun GeoParquet-tiedoston polku tai None, jos aineisto ei muuttunut.
    """
    kansio = juuri / lahde.id
    kansio.mkdir(parents=True, exist_ok=True)
    tiiviste = hashlib.sha256(gdf.to_wkb(hex=True).to_json(force_ascii=False).encode("utf-8")).hexdigest()
    meta_polku = kansio / "metatiedot.json"
    if meta_polku.exists():
        edellinen = json.loads(meta_polku.read_text(encoding="utf-8"))
        if edellinen.get("sha256") == tiiviste:
            logger.info("Lähde %s ei ole muuttunut – ei tallenneta.", lahde.id)
            return None

    data_polku = kansio / f"{lahde.id}.parquet"
    gdf.to_parquet(data_polku, index=False)
    metatiedot = {
        **{k: v for k, v in asdict(lahde).items() if k not in {"api_avain_env", "lisaparametrit"}},
        "url": peita_avaimet(lahde.url),
        "haettu": datetime.now(UTC).isoformat(timespec="seconds"),
        "kohteita": len(gdf),
        "sha256": tiiviste,
    }
    meta_polku.write_text(json.dumps(metatiedot, ensure_ascii=False, indent=2), encoding="utf-8")
    return data_polku
