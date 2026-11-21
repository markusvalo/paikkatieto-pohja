"""Palvelun kuvaus ja vaihtuvat tasonimet (lahteet) sekä komento paikka kokoelmat ilman verkkoa."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from paikka import cli, lahteet

CAPS = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:ows="http://www.opengis.net/ows/1.1">
  <ows:ServiceIdentification><ows:Title>Testi</ows:Title></ows:ServiceIdentification>
  <wfs:FeatureTypeList>
    <wfs:FeatureType><wfs:Name>ns:Ruudukko_2023</wfs:Name></wfs:FeatureType>
    <wfs:FeatureType><wfs:Name>ns:Ruudukko_2024</wfs:Name></wfs:FeatureType>
    <wfs:FeatureType><wfs:Name>ns:Ruudukko_luonnos</wfs:Name></wfs:FeatureType>
    <wfs:FeatureType><wfs:Name>ns:Varanto_20170811</wfs:Name></wfs:FeatureType>
    <wfs:FeatureType><wfs:Name>ns:Varanto_I_2024</wfs:Name></wfs:FeatureType>
    <wfs:FeatureType><wfs:Name>ns:Varanto_22025</wfs:Name></wfs:FeatureType>
    <wfs:FeatureType><wfs:Name>ns:Varanto_12026</wfs:Name></wfs:FeatureType>
  </wfs:FeatureTypeList>
</wfs:WFS_Capabilities>"""
CAPS_10 = """<WFS_Capabilities version="1.0.0" xmlns="http://www.opengis.net/wfs">
<Service><Name>WFS</Name></Service>
<FeatureTypeList><FeatureType><Name>GIS:Kaupunginosat</Name></FeatureType></FeatureTypeList></WFS_Capabilities>"""


class _Istunto:
    def __init__(self, teksti: str) -> None:
        self.teksti = teksti
        self.params: dict[str, Any] = {}

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: float = 0) -> requests.Response:
        self.params = dict(params or {})
        r = requests.Response()
        r.status_code = 200
        r._content = self.teksti.encode("utf-8")
        r.encoding = "utf-8"
        return r


def _lahde(kokoelma: str = "ns:Ruudukko_{vuosi}", tyyppi: str = "wfs") -> lahteet.Lahde:
    return lahteet.Lahde(
        id="t", nimi="t", tyyppi=tyyppi, url="https://esim.fi/wfs", epsg=3879, lisenssi="x", attribuutio="x",
        kokoelma=kokoelma,
    )  # fmt: skip


def test_tasonimet_eri_versioista() -> None:
    assert lahteet.tasonimet(CAPS)[:2] == ["ns:Ruudukko_2023", "ns:Ruudukko_2024"]
    assert lahteet.tasonimet(CAPS_10) == ["GIS:Kaupunginosat"]  # palvelun nimi "WFS" ei ole taso
    with pytest.raises(ValueError, match="XML"):
        lahteet.tasonimet("<html")


def test_hae_capabilities() -> None:
    istunto = _Istunto(CAPS)
    assert "Ruudukko_2024" in lahteet.hae_capabilities(_lahde(), istunto=istunto)
    assert istunto.params["request"] == "GetCapabilities" and istunto.params["version"] == "2.0.0"
    with pytest.raises(ValueError, match="ei ole WFS"):
        lahteet.hae_capabilities(_lahde(tyyppi="ogc_api_features"))


def test_vuodet_ja_paikkamerkit() -> None:
    nimet = lahteet.tasonimet(CAPS)
    assert lahteet.paikkamerkin_arvot(nimet, "ns:Ruudukko_{vuosi}", "vuosi") == ["2023", "2024", "luonnos"]
    assert lahteet.vuodet(nimet, "ns:Ruudukko_{vuosi}") == [2023, 2024]
    with pytest.raises(ValueError, match="ei ole tasoa"):
        lahteet.vuodet(nimet, "ns:Muu_{vuosi}")
    with pytest.raises(ValueError, match="paikkamerkkiä"):
        lahteet.paikkamerkin_arvot(nimet, "ns:Ruudukko", "vuosi")


@pytest.mark.parametrize(
    ("tunniste", "odotettu"),
    [("12026", (2026, 1)), ("22025", (2025, 2)), ("I_2024", (2024, 1)), ("II_2024", (2024, 2)),
     ("20170811", (2017, 2)), ("20170301", (2017, 1)), ("luonnos", None)],
)  # fmt: skip
def test_jakso(tunniste: str, odotettu: tuple[int, int] | None) -> None:
    assert lahteet.jakso(tunniste) == odotettu


def test_uusin_jakso() -> None:
    assert lahteet.uusin_jakso(lahteet.tasonimet(CAPS), "ns:Varanto_{jakso}") == ("12026", (2026, 1))


def test_taydenna_ja_haku_vaatii_taydennyksen() -> None:
    lahde = _lahde()
    assert lahteet.taydenna(lahde, vuosi=2024).kokoelma == "ns:Ruudukko_2024"
    assert lahde.kokoelma == "ns:Ruudukko_{vuosi}"  # alkuperäinen ei muutu
    with pytest.raises(ValueError, match="paikkamerkille"):
        lahteet.taydenna(lahde, jakso="12026")
    with pytest.raises(ValueError, match="taydenna"):
        lahteet.hae(lahde, istunto=_Istunto("{}"))


def test_kuvaa_kokoelma() -> None:
    class _Ogc:
        def get(self, url: str, params: dict[str, Any] | None = None, timeout: float = 0) -> requests.Response:
            r = requests.Response()
            r.status_code = 200
            if url.endswith("/items"):
                r._content = b'{"features": [{"properties": {"tunnus": "1", "nimi": "\\u00e4"}}]}'
            else:
                r._content = b'{"title": "Kokoelma", "crs": ["http://www.opengis.net/def/crs/EPSG/0/3067"]}'
            return r

    lahde = lahteet.Lahde(
        id="o", nimi="o", tyyppi="ogc_api_features", url="https://esim.fi", kokoelma="k", epsg=3067, lisenssi="x",
        attribuutio="x",
    )  # fmt: skip
    k = lahteet.kuvaa_kokoelma(lahde, istunto=_Ogc())
    assert k["tukee_epsg"] and k["otsikko"] == "Kokoelma" and k["kentat"] == {"tunnus": "1", "nimi": "ä"}
    with pytest.raises(ValueError, match="OGC"):
        lahteet.kuvaa_kokoelma(_lahde())


def test_cli_kokoelmat(tmp_path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    rekisteri = tmp_path / "lahteet.yaml"
    rekisteri.write_text(
        "lahteet:\n"
        "  ruudut:\n    nimi: r\n    tyyppi: wfs\n    url: https://esim.fi/wfs\n    kokoelma: 'ns:Ruudukko_{vuosi}'\n"
        "    epsg: 3879\n    lisenssi: x\n    attribuutio: x\n"
        "  puuttuu:\n    nimi: p\n    tyyppi: wfs\n    url: https://esim.fi/wfs\n    kokoelma: 'ns:Ei'\n"
        "    epsg: 3879\n    lisenssi: x\n    attribuutio: x\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lahteet, "hae_capabilities", lambda lahde, versio="2.0.0": CAPS)
    assert cli.main(["--rekisteri", str(rekisteri), "kokoelmat", "ruudut"]) == 0
    assert "2023, 2024" in capsys.readouterr().out
    assert cli.main(["--rekisteri", str(rekisteri), "kokoelmat"]) == 1  # puuttuva taso kaataa
    assert "ns:Ei puuttuu" in capsys.readouterr().out
