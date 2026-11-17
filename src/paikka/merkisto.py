"""Merkistöt ja suomenkielinen teksti.

Käytäntö (ks. docs/adr/0002-merkistot.md):
    * Kaikki tekstitiedostot UTF-8, Unicode-normalisointi NFC.
    * CSV Exceliin ja Power BI:hin UTF-8 BOM:lla (utf-8-sig), muuten Excel tulkitsee
      ä:n ja ö:n väärin.
    * Vanhat aineistot (Shapefile ilman .cpg:tä, MapInfo, vanhat CSV:t) ovat usein
      Windows-1252- tai ISO-8859-1/-15-koodattuja: luetaan tunnistaen ja tallennetaan UTF-8:na.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

# Tyypilliset merkit, kun UTF-8 on luettu Windows-1252:na (ä→Ã¤ jne.) tai tavu on hukattu.
MOJIBAKE_MERKIT: tuple[str, ...] = (
    "Ã¤",
    "Ã¶",
    "Ã¥",
    "Ã„",
    "Ã–",
    "Ã…",
    "Ã©",
    "Ã¼",
    "â€“",
    "â€",
    "�",
)

# Kokeilujärjestys tuntemattomalle tiedostolle. latin-1 ei epäonnistu koskaan, joten se on viimeinen.
KOODAUKSET_KOKEILU: tuple[str, ...] = ("utf-8-sig", "cp1252", "latin-1")

# Suomalainen lajittelu (CLDR fi): å, ä, ö z:n jälkeen; ü=y, æ=ä, ø=ö.
# Merkit {, |, } ovat Unicodessa heti z:n jälkeen.
_LAJITTELU_KORVAUKSET = str.maketrans({"å": "{", "ä": "|", "æ": "|", "ö": "}", "ø": "}", "ü": "y"})

type CsvMurre = Literal["powerbi", "excel_fi"]


@dataclass(frozen=True)
class TekstiOngelma:
    """Yksittäinen tekstisarakkeen ongelma."""

    sarake: str
    rivi: object
    tyyppi: Literal["mojibake", "ei_nfc", "ohjausmerkki"]
    arvo: str


def lue_teksti(polku: Path) -> tuple[str, str]:
    """Lue tekstitiedosto ja tunnista merkistö.

    Returns:
        (sisältö NFC-normalisoituna, käytetty koodaus)
    """
    data = polku.read_bytes()
    for koodaus in KOODAUKSET_KOKEILU:
        try:
            teksti = data.decode(koodaus)
        except UnicodeDecodeError:
            continue
        if koodaus != "utf-8-sig":
            logger.warning("%s ei ole UTF-8 – luettu koodauksella %s. Tarkista ääkköset.", polku, koodaus)
        return unicodedata.normalize("NFC", teksti), koodaus
    raise AssertionError("latin-1 purkaa minkä tahansa tavujonon – tänne ei pitäisi päätyä.")


def on_mojibake(teksti: str) -> bool:
    """Sisältääkö teksti tyypillisiä väärin tulkitun merkistön jälkiä."""
    return any(m in teksti for m in MOJIBAKE_MERKIT)


def korjaa_mojibake(teksti: str) -> str:
    """Korjaa kerran väärin tulkittu UTF-8 (esim. 'PÃ¤ijÃ¤nne' → 'Päijänne').

    Palauttaa alkuperäisen, jos korjaus ei onnistu tai tekstissä ei ole mojibakea.
    """
    if not on_mojibake(teksti):
        return teksti
    for vali in ("cp1252", "latin-1"):
        try:
            return teksti.encode(vali).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    logger.warning("Mojibakea ei voitu korjata automaattisesti: %r", teksti[:80])
    return teksti


def normalisoi(teksti: str) -> str:
    """NFC-normalisointi (esim. macOS:n hajotettu 'a'+'̈' → 'ä')."""
    return unicodedata.normalize("NFC", teksti)


def suomi_lajitteluavain(teksti: str) -> str:
    """Lajitteluavain suomalaiseen aakkosjärjestykseen (… x, y, z, å, ä, ö).

    Esimerkki: ``sorted(nimet, key=suomi_lajitteluavain)``
    """
    perus = normalisoi(teksti).casefold().translate(_LAJITTELU_KORVAUKSET)
    # Muut tarkkeet (é, è, á…) lajitellaan perusmerkkinsä mukaan.
    hajotettu = unicodedata.normalize("NFD", perus)
    return "".join(m for m in hajotettu if not unicodedata.combining(m))


def _tekstisarakkeet(df: pd.DataFrame) -> list[str]:
    return [s for s in df.columns if s != "geometry" and (df[s].dtype == object or pd.api.types.is_string_dtype(df[s]))]


def tarkista_tekstit(df: pd.DataFrame, max_ongelmia: int = 50) -> list[TekstiOngelma]:
    """Etsi mojibakea, normalisoimatonta tekstiä ja ohjausmerkkejä tekstisarakkeista.

    Monimutkaisuus O(rivit × tekstisarakkeet); riittää koko Suomen aineistoille.
    """
    ongelmat: list[TekstiOngelma] = []
    tutkittavat: list[tuple[str, pd.Series]] = [(s, df[s].dropna()) for s in _tekstisarakkeet(df)]
    # Myös sarakenimet: Shapefile- ja Excel-lähteissä ne ovat usein rikki.
    tutkittavat.append(("<sarakenimet>", pd.Series([str(s) for s in df.columns], dtype=object)))
    for sarake, arvot in tutkittavat:
        for rivi, arvo in arvot.items():
            if not isinstance(arvo, str):
                continue
            if on_mojibake(arvo):
                ongelmat.append(TekstiOngelma(sarake, rivi, "mojibake", arvo))
            elif normalisoi(arvo) != arvo:
                ongelmat.append(TekstiOngelma(sarake, rivi, "ei_nfc", arvo))
            elif any(unicodedata.category(m) == "Cc" and m not in "\t\n\r" for m in arvo):
                ongelmat.append(TekstiOngelma(sarake, rivi, "ohjausmerkki", arvo))
            if len(ongelmat) >= max_ongelmia:
                return ongelmat
    return ongelmat


def siivoa_tekstit(df: pd.DataFrame, korjaa_mojibakea: bool = True) -> pd.DataFrame:
    """Normalisoi tekstisarakkeet (NFC) ja sarakenimet sekä korjaa mojibake. Palauttaa kopion."""
    tulos = df.copy()
    for sarake in _tekstisarakkeet(tulos):

        def _siivoa(arvo: object) -> object:
            if not isinstance(arvo, str):
                return arvo
            arvo = normalisoi(arvo)
            return korjaa_mojibake(arvo) if korjaa_mojibakea else arvo

        tulos[sarake] = tulos[sarake].map(_siivoa)
    tulos.columns = [normalisoi(str(s)) if s != "geometry" else s for s in tulos.columns]
    return tulos


def kirjoita_csv(df: pd.DataFrame, polku: Path, murre: CsvMurre = "powerbi") -> None:
    """Kirjoita CSV, joka aukeaa oikein Excelissä ja Power BI:ssä.

    Args:
        df: Kirjoitettava taulukko (ilman geometriasaraketta).
        polku: Kohdetiedosto.
        murre: ``powerbi`` = pilkku erottimena ja piste desimaalina (kieliasetuksista riippumaton);
            ``excel_fi`` = puolipiste erottimena ja pilkku desimaalina (suomalainen Excel).
    """
    erotin, desimaali = (",", ".") if murre == "powerbi" else (";", ",")
    polku.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(polku, sep=erotin, decimal=desimaali, index=False, encoding="utf-8-sig", lineterminator="\r\n")
