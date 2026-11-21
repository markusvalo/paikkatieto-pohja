"""Komentorivi: ``python -m paikka <komento>`` tai ``pixi run paikka <komento>``.

Esimerkit::

    paikka lahteet
    paikka kokoelmat hki_rakennukset
    paikka hae hki_rakennukset --rajaus 25496000 6672000 25498000 6674000
    paikka tarkista data/raw/hki_rakennukset/hki_rakennukset.parquet --alue suomi
    paikka ehdota-crs aineisto.gpkg
    paikka muunna aineisto.gpkg ulos.parquet --crs tm35
    paikka vie data/processed/x.parquet data/products/x.csv --muoto powerbi
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import geopandas as gpd
import requests

from paikka import __version__, lahteet, tarkistus, vienti
from paikka import crs as crs_mod

# Oletuspolut suhteessa työhakemistoon (projektin juuri). Kirjasto ei oleta omaa sijaintiaan,
# koska se asennetaan projekteihin pakettina (ADR 0004).
REKISTERI = Path("config") / "lahteet.yaml"
RAAKADATA = Path("data") / "raw"


def _rekisteri(a: argparse.Namespace) -> dict[str, lahteet.Lahde]:
    """Lue lähderekisteri valitsimen ``--rekisteri`` polusta.

    Raises:
        FileNotFoundError: Jos rekisteriä ei ole (komento ajettu muualta kuin projektin juuresta).
    """
    if not a.rekisteri.exists():
        raise FileNotFoundError(
            f"Lähderekisteriä ei löydy: {a.rekisteri.resolve()}. Aja komento projektin juuresta tai anna --rekisteri."
        )
    return lahteet.lataa_rekisteri(a.rekisteri)


logger = logging.getLogger("paikka")


def _lue(polku: Path) -> gpd.GeoDataFrame:
    if polku.suffix == ".parquet":
        return gpd.read_parquet(polku)
    return gpd.read_file(polku, engine="pyogrio")


def _komento_lahteet(a: argparse.Namespace) -> int:
    for l in _rekisteri(a).values():  # noqa: E741
        epsg = f"EPSG:{l.epsg}" if l.epsg else "sijainniton"
        print(f"{l.id:28} {epsg:11} {l.lisenssi[:12]:12} {l.nimi}")
    return 0


def _komento_hae(a: argparse.Namespace) -> int:
    rekisteri = _rekisteri(a)
    if a.lahde not in rekisteri:
        print(f"Tuntematon lähde '{a.lahde}'. Katso: paikka lahteet", file=sys.stderr)
        return 2
    lahde = rekisteri[a.lahde]
    gdf = lahteet.hae(lahde, rajaus=tuple(a.rajaus) if a.rajaus else None, rajaus_epsg=a.rajaus_epsg)
    ongelmat = tarkistus.tarkista(gdf, alue=None)
    for o in ongelmat:
        print(o)
    polku = lahteet.tallenna_raaka(gdf, lahde, a.raakadata)
    print(f"Tallennettu: {polku}" if polku else "Ei muutoksia edelliseen hakuun.")
    return 1 if any(o.vakavuus == "virhe" for o in ongelmat) else 0


def _kuvaa_wfs(lahde: lahteet.Lahde) -> bool:
    """Tulosta WFS-lähteen tason tila palvelussa. Palauttaa, löytyikö taso."""
    nimet = lahteet.tasonimet(lahteet.hae_capabilities(lahde, versio="1.0.0" if lahde.tyyppi == "wfs_gml" else "2.0.0"))
    kokoelma = lahde.kokoelma or ""
    merkit = re.findall(r"\{(\w+)\}", kokoelma)
    if merkit:
        arvot = lahteet.paikkamerkin_arvot(nimet, kokoelma, merkit[0])
        print(f"  {'✓' if arvot else '✗'} {kokoelma}: {', '.join(arvot) or 'ei vastaavia tasoja'}")
        return bool(arvot)
    loytyi = kokoelma in nimet
    print(f"  {'✓' if loytyi else '✗'} {kokoelma} {'löytyi' if loytyi else 'puuttuu'} ({len(nimet)} tasoa palvelussa)")
    return loytyi


def _komento_kokoelmat(a: argparse.Namespace) -> int:
    rekisteri = _rekisteri(a)
    haettavat = ("ogc_api_features", "wfs", "wfs_gml")
    tunnukset = a.lahteet or [t for t, lh in rekisteri.items() if lh.tyyppi in haettavat]
    paluu = 0
    for tunnus in tunnukset:
        if tunnus not in rekisteri:
            print(f"✗ {tunnus}: ei rekisterissä")
            paluu = 1
            continue
        lahde = rekisteri[tunnus]
        print(f"\n{tunnus} ({lahde.tyyppi})")
        try:
            if lahde.tyyppi == "ogc_api_features":
                k = lahteet.kuvaa_kokoelma(lahde)
                ok = k["tukee_epsg"]
                print(f"  {k['kokoelma']} ({k['otsikko']})")
                tuetut = ", ".join(c.rsplit("/", 1)[-1] for c in k["crs"])
                print(f"  {'✓' if ok else '✗'} EPSG:{lahde.epsg} tuettu. CRS:t: {tuetut}")
                for nimi, arvo in k["kentat"].items():
                    print(f"    {nimi:40} {str(arvo)[:50]}")
            elif lahde.tyyppi in ("wfs", "wfs_gml"):
                ok = _kuvaa_wfs(lahde)
            else:
                print("  (ei tarkistettavaa: lähdetyyppiä ei haeta palvelusta)")
                ok = True
        except (requests.RequestException, RuntimeError, ValueError) as e:  # raportoi kaikki, vaikka yksi kaatuu
            print(f"  ✗ {e}")
            ok = False
        paluu |= 0 if ok else 1
    return paluu


def _komento_tarkista(a: argparse.Namespace) -> int:
    ongelmat = tarkistus.tarkista(
        _lue(a.tiedosto), alue=None if a.alue == "ei" else a.alue, pakolliset=a.pakolliset or ()
    )
    for o in ongelmat:
        print(o)
    if not ongelmat:
        print("OK – ei havaittuja ongelmia.")
    return 1 if any(o.vakavuus == "virhe" for o in ongelmat) else 0


def _komento_ehdota(a: argparse.Namespace) -> int:
    p = crs_mod.ehdota_crs(_lue(a.tiedosto))
    print(f"{p.nimi} (EPSG:{p.epsg}) – {p.kuvaus}")
    return 0


def _komento_muunna(a: argparse.Namespace) -> int:
    gdf = crs_mod.muunna(_lue(a.tiedosto), a.crs)
    if a.ulos.suffix == ".parquet":
        vienti.vie_geoparquet(gdf, a.ulos)
    else:
        vienti.vie_geopackage(gdf, a.ulos)
    print(f"Muunnettu → {a.ulos} (EPSG:{gdf.crs.to_epsg()})")
    return 0


def _komento_vie(a: argparse.Namespace) -> int:
    vienti.VIENNIT[a.muoto](_lue(a.tiedosto), a.ulos)
    print(f"Viety → {a.ulos}")
    return 0


def rakenna_parseri() -> argparse.ArgumentParser:
    """Komentorivin määrittely."""
    p = argparse.ArgumentParser(prog="paikka", description="Paikkatietoprojektin työkalut")
    p.add_argument("-v", "--verbose", action="store_true", help="Näytä DEBUG-loki")
    p.add_argument("--versio", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--rekisteri", type=Path, default=REKISTERI, help=f"Lähderekisteri (oletus: {REKISTERI} työhakemistossa)"
    )
    ali = p.add_subparsers(dest="komento", required=True)

    ali.add_parser("lahteet", help="Listaa lähderekisteri").set_defaults(f=_komento_lahteet)

    h = ali.add_parser("hae", help="Hae lähde ja tallenna raakadataksi")
    h.add_argument("lahde")
    h.add_argument("--rajaus", nargs=4, type=float, metavar=("MINX", "MINY", "MAXX", "MAXY"))
    h.add_argument("--rajaus-epsg", type=int)
    h.add_argument("--raakadata", type=Path, default=RAAKADATA, help=f"Tallennuskansio (oletus: {RAAKADATA})")
    h.set_defaults(f=_komento_hae)

    k = ali.add_parser("kokoelmat", help="Tarkista lähteiden kokoelmat ja tasot palvelussa (CRS:t, kentät, vuodet)")
    k.add_argument("lahteet", nargs="*", help="Lähdetunnukset (oletus: kaikki OGC API- ja WFS-lähteet)")
    k.set_defaults(f=_komento_kokoelmat)

    t = ali.add_parser("tarkista", help="Tarkista aineiston laatu")
    t.add_argument("tiedosto", type=Path)
    t.add_argument("--alue", choices=["suomi", "eurooppa", "ei"], default="suomi")
    t.add_argument("--pakolliset", nargs="*")
    t.set_defaults(f=_komento_tarkista)

    e = ali.add_parser("ehdota-crs", help="Ehdota analyysin koordinaattijärjestelmää")
    e.add_argument("tiedosto", type=Path)
    e.set_defaults(f=_komento_ehdota)

    m = ali.add_parser("muunna", help="Muunna koordinaattijärjestelmä")
    m.add_argument("tiedosto", type=Path)
    m.add_argument("ulos", type=Path)
    m.add_argument("--crs", required=True, help=f"Profiili tai EPSG: {', '.join(crs_mod.PROFIILIT)}")
    m.set_defaults(f=_komento_muunna)

    v = ali.add_parser("vie", help="Vie lopputuotteeksi")
    v.add_argument("tiedosto", type=Path)
    v.add_argument("ulos", type=Path)
    v.add_argument("--muoto", choices=sorted(vienti.VIENNIT), required=True)
    v.set_defaults(f=_komento_vie)
    return p


def main(argv: list[str] | None = None) -> int:
    """Komentorivin aloituspiste."""
    args = rakenna_parseri().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.f(args)
    except (ValueError, KeyError, RuntimeError, FileNotFoundError, tarkistus.TarkistusVirhe) as e:
        logger.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
