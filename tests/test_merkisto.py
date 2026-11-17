from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

from paikka import merkisto


def test_mojibake_tunnistus_ja_korjaus() -> None:
    rikki = "Päijänne".encode().decode("cp1252")
    assert rikki == "PÃ¤ijÃ¤nne"
    assert merkisto.on_mojibake(rikki)
    assert merkisto.korjaa_mojibake(rikki) == "Päijänne"


def test_ehjaa_tekstia_ei_muuteta() -> None:
    for teksti in ("Päijänne", "Åland", "Öljysatama", "", "Ünal"):
        assert merkisto.korjaa_mojibake(teksti) == teksti


def test_lue_windows1252_tiedosto(tmp_path: Path) -> None:
    polku = tmp_path / "vanha.csv"
    polku.write_bytes("kunta;nimi\n091;Hämeenlinnantie\n".encode("cp1252"))
    teksti, koodaus = merkisto.lue_teksti(polku)
    assert koodaus == "cp1252"
    assert "Hämeenlinnantie" in teksti


def test_lue_utf8_bom(tmp_path: Path) -> None:
    polku = tmp_path / "bom.csv"
    polku.write_bytes("﻿nimi\nÄänekoski\n".encode())
    teksti, koodaus = merkisto.lue_teksti(polku)
    assert koodaus == "utf-8-sig"
    assert teksti.startswith("nimi")


def test_nfc_normalisointi() -> None:
    hajotettu = unicodedata.normalize("NFD", "Ähtäri")
    assert hajotettu != "Ähtäri"
    assert merkisto.normalisoi(hajotettu) == "Ähtäri"


def test_suomalainen_lajittelu() -> None:
    nimet = ["Öljy", "Åke", "Ärrä", "Zeta", "auto", "Ylläs", "Ümit", "Élise", "Ewa"]
    tulos = sorted(nimet, key=merkisto.suomi_lajitteluavain)
    assert tulos == ["auto", "Élise", "Ewa", "Ylläs", "Ümit", "Zeta", "Åke", "Ärrä", "Öljy"]


def test_tarkista_tekstit_loytaa_ongelmat() -> None:
    df = pd.DataFrame(
        {
            "nimi": ["Kallio", "PÃ¤ijÃ¤nne", unicodedata.normalize("NFD", "Ähtäri"), "rivi\x00"],
            "luku": [1, 2, 3, 4],
        }
    )
    tyypit = [o.tyyppi for o in merkisto.tarkista_tekstit(df)]
    assert tyypit == ["mojibake", "ei_nfc", "ohjausmerkki"]


def test_rikkinainen_sarakenimi_havaitaan() -> None:
    df = pd.DataFrame({"KerrosalaÃ¤": [1]})
    assert merkisto.tarkista_tekstit(df)[0].sarake == "<sarakenimet>"


def test_csv_powerbi_bom_ja_aakkoset(tmp_path: Path) -> None:
    polku = tmp_path / "pbi.csv"
    merkisto.kirjoita_csv(pd.DataFrame({"kunta": ["Hämeenlinna"], "ala": [1.5]}), polku)
    data = polku.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert "Hämeenlinna,1.5" in data.decode("utf-8-sig")


def test_csv_excel_fi_desimaalipilkku(tmp_path: Path) -> None:
    polku = tmp_path / "excel.csv"
    merkisto.kirjoita_csv(pd.DataFrame({"kunta": ["Åänekoski"], "ala": [1.5]}), polku, murre="excel_fi")
    assert "Åänekoski;1,5" in polku.read_text(encoding="utf-8-sig")
