"""Kiinteistötunnukset: jäsennys, esitysmuoto ja kiinteistölaji tunnuksesta.

Kiinteistötunnus on neliosainen: kunta (3) – sijaintialue (3) – ryhmä (4) – yksikkö (4). Tallennusmuoto on
14 numeroa ilman väliviivoja (``09100100010001``), ja esitysmuodossa osat erotetaan väliviivoin ilman
etunollia (``91-1-1-1``).

Kiinteistölaji päätellään tunnuksesta Maanmittauslaitoksen kiinteistörekisteriohjeen mukaan
(kohdat 6.1.2–6.1.4):

    yleinen alue      asemakaava-alueella, ryhmä 9901–9909 (``YLEISET_ALUEET``)
    erityisyksikkö    sijaintialue 872–893 (``ERITYISYKSIKOT``)
    tontti            sijaintialue on kunnan kaupunginosa (asemakaava-alue)
    tila              muut

Kaupunginosien numerot ovat kuntakohtaisia, joten ne annetaan parametrina (esim. kunnan aluejaosta).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

YLEISET_ALUEET: dict[int, str] = {
    9901: "katualue",
    9902: "tori ja katuaukio",
    9903: "puisto tai muu virkistysalue",
    9904: "urheilualue",
    9905: "loma- ja matkailualue",
    9906: "liikennealue",
    9907: "vaara-alue",
    9908: "erityisalue ja suojelualue",
    9909: "vesialue",
}
ERITYISYKSIKOT: dict[int, str] = {
    872: "erillinen vesijättö",
    874: "yhteismetsä",
    876: "yhteinen alue",
    878: "yhteinen alue",
    881: "kirkon tai hautausmaan alue",
    882: "yleiseen tarpeeseen erotettu alue",
    884: "entinen yleinen tiealue",
    891: "suojelualuekiinteistö",
    893: "valtion metsämaa",
}
PITUUDET = (3, 3, 4, 4)
_ESITYS = re.compile(r"^(\d{1,3})-(\d{1,3})-(\d{1,4})-(\d{1,4})$")


def normalisoi(tunnus: str | int) -> str:
    """Tunnus 14-numeroiseen tallennusmuotoon.

    Hyväksyy tallennusmuodon (``09100100010001``, myös kokonaislukuna, jolloin etunollat puuttuvat) ja
    esitysmuodon (``91-1-1-1`` tai ``091-001-0001-0001``).

    Raises:
        ValueError: Jos tunnus ei ole kumpaakaan muotoa.
    """
    teksti = str(tunnus).strip()
    if m := _ESITYS.match(teksti):
        return "".join(osa.zfill(n) for osa, n in zip(m.groups(), PITUUDET, strict=True))
    if teksti.isdigit() and 11 <= len(teksti) <= 14:  # kokonaislukuna kunnan etunollat puuttuvat
        return teksti.zfill(14)
    raise ValueError(f"Virheellinen kiinteistötunnus: {tunnus!r}")


def osat(tunnus: str | int) -> tuple[int, int, int, int]:
    """Tunnuksen osat (kunta, sijaintialue, ryhmä, yksikkö) kokonaislukuina."""
    t = normalisoi(tunnus)
    return int(t[:3]), int(t[3:6]), int(t[6:10]), int(t[10:])


def esitysmuoto(tunnus: str | int) -> str:
    """Esitysmuoto väliviivoin ilman etunollia: ``09100100010001`` → ``91-1-1-1``."""
    return "-".join(str(o) for o in osat(tunnus))


def kiinteistolaji(tunnukset: pd.Series, kaupunginosat: Iterable[int]) -> pd.DataFrame:
    """Laji ja tunnuksen kaupunginosa ja kortteli 14-numeroisista tunnuksista.

    Args:
        tunnukset: 14-numeroiset tunnukset (``normalisoi``).
        kaupunginosat: Kunnan kaupunginosien numerot (asemakaava-alueen sijaintialueet).

    Returns:
        Sarakkeet ``laji``, ``yleisen_alueen_laji``, ``tunnuksen_kaupunginosa`` (asemakaava-alueella) ja
        ``tunnuksen_kortteli`` (tonteilla, ryhmänumero). Indeksi on sama kuin syötteellä.

    Raises:
        ValueError: Jos jokin tunnus ei ole 14 numeroa.
    """
    t = tunnukset.astype("string")
    virheelliset = t[~t.str.fullmatch(r"\d{14}").fillna(False)]
    if len(virheelliset):
        raise ValueError(f"Virheellisiä kiinteistötunnuksia (normalisoi ensin): {virheelliset.head(3).tolist()}")
    sijainti = t.str[3:6].astype(int)
    ryhma = t.str[6:10].astype(int)
    asemakaava = sijainti.isin(set(kaupunginosat))
    yleinen = asemakaava & ryhma.isin(YLEISET_ALUEET)
    erityinen = sijainti.isin(ERITYISYKSIKOT)
    laji = pd.Series("tila", index=t.index, dtype="string")
    laji[asemakaava] = "tontti"
    laji[yleinen] = "yleinen alue"
    laji[erityinen] = sijainti[erityinen].map(ERITYISYKSIKOT)
    return pd.DataFrame(
        {
            "laji": laji,
            "yleisen_alueen_laji": ryhma.where(yleinen).map(YLEISET_ALUEET).astype("string"),
            "tunnuksen_kaupunginosa": sijainti.astype("string").where(asemakaava),
            "tunnuksen_kortteli": ryhma.astype("string").where(laji == "tontti"),
        },
        index=t.index,
    )
