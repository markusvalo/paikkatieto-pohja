"""Kiinteistötunnukset ja kiinteistölaji (paikka.kiinteisto)."""

from __future__ import annotations

import pandas as pd
import pytest

from paikka import kiinteisto as k

TONTTI = "04901200160002"  # 49-12-16-2: kaupunginosa 12, kortteli 16
YLEINEN = "04901299010000"  # 49-12-9901-0: katualue
TILA = "04941200010023"  # 49-412-1-23: kylä 412
YHTEINEN = "04987600010000"  # 49-876-1-0: erityisyksikkö


@pytest.mark.parametrize("syote", ["49-12-16-2", "049-012-0016-0002", "04901200160002", 4901200160002, " 49-12-16-2 "])
def test_normalisoi(syote: str | int) -> None:
    assert k.normalisoi(syote) == TONTTI


@pytest.mark.parametrize("syote", ["49-12-16", "4901200160002x", "1234-1-1-1", "", "091001"])
def test_virheellinen_tunnus(syote: str) -> None:
    with pytest.raises(ValueError, match="Virheellinen"):
        k.normalisoi(syote)


def test_osat_ja_esitysmuoto() -> None:
    assert k.osat(TONTTI) == (49, 12, 16, 2)
    assert k.esitysmuoto(TONTTI) == "49-12-16-2"
    assert k.esitysmuoto("09100100010001") == "91-1-1-1"


def test_kiinteistolaji() -> None:
    laji = k.kiinteistolaji(pd.Series([TONTTI, YLEINEN, TILA, YHTEINEN], index=[5, 6, 7, 8]), kaupunginosat=[12])
    assert laji.index.tolist() == [5, 6, 7, 8]
    assert laji["laji"].tolist() == ["tontti", "yleinen alue", "tila", "yhteinen alue"]
    assert laji["yleisen_alueen_laji"].iloc[1] == "katualue"
    assert laji["tunnuksen_kaupunginosa"].tolist()[:3] == ["12", "12", pd.NA]
    assert laji["tunnuksen_kortteli"].iloc[0] == "16"
    assert pd.isna(laji["tunnuksen_kortteli"].iloc[1])  # yleisellä alueella ei korttelia


def test_kiinteistolaji_vaatii_tallennusmuodon() -> None:
    with pytest.raises(ValueError, match="normalisoi"):
        k.kiinteistolaji(pd.Series(["49-12-16-2"]), kaupunginosat=[12])
