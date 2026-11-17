from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import pytest

from paikka import lahteet

JUURI = Path(__file__).resolve().parents[1]


class _Vastaus:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._data


class _ValeIstunto:
    """Palauttaa ennalta määritellyt sivut ja kirjaa kutsut."""

    def __init__(self, sivut: list[dict[str, Any]]) -> None:
        self.sivut = sivut
        self.kutsut: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: float = 0) -> _Vastaus:
        self.kutsut.append((url, dict(params or {})))
        return _Vastaus(self.sivut[len(self.kutsut) - 1])


def _kohde(x: float, y: float, nimi: str) -> dict[str, Any]:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]}, "properties": {"nimi": nimi}}


def test_rekisteri_latautuu() -> None:
    rekisteri = lahteet.lataa_rekisteri(JUURI / "config" / "lahteet.yaml")
    assert {"mml_rakennukset", "hki_rakennukset", "gisco_nuts2"} <= set(rekisteri)
    assert all(l.lisenssi and l.attribuutio for l in rekisteri.values())  # noqa: E741


def test_ogc_sivutus_ja_akselikorjaus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTI_AVAIN", "salainen")
    lahde = lahteet.Lahde(
        id="testi",
        nimi="Testi",
        tyyppi="ogc_api_features",
        url="https://esim.fi/features",
        kokoelma="rakennus",
        epsg=3879,
        lisenssi="CC BY 4.0",
        attribuutio="Testi",
        api_avain_env="TESTI_AVAIN",
    )
    # Rajapinta palauttaa GK25FIN:n EPSG-järjestyksessä (pohjoinen, itä) – yleinen sudenkuoppa.
    istunto = _ValeIstunto(
        [
            {
                "features": [_kohde(6_673_000, 25_496_800, "Kallio")],
                "links": [{"rel": "next", "href": "https://esim.fi/sivu2"}],
            },
            {"features": [_kohde(6_673_100, 25_496_900, "Sörnäinen")], "links": []},
        ]
    )
    gdf = lahteet.hae(lahde, istunto=istunto)
    assert len(gdf) == 2
    assert gdf.geometry.iloc[0].x == 25_496_800  # korjattu x=itä
    assert istunto.kutsut[0][1]["api-key"] == "salainen"
    assert istunto.kutsut[1] == ("https://esim.fi/sivu2", {"api-key": "salainen"})


def test_puuttuva_api_avain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PUUTTUU", raising=False)
    lahde = lahteet.Lahde(
        id="x",
        nimi="x",
        tyyppi="wfs",
        url="https://x",
        kokoelma="t",
        epsg=3067,
        lisenssi="x",
        attribuutio="x",
        api_avain_env="PUUTTUU",
    )
    with pytest.raises(RuntimeError, match="PUUTTUU"):
        lahteet.hae(lahde, istunto=_ValeIstunto([{}]))


def test_avaimet_peitetaan() -> None:
    assert lahteet.peita_avaimet("https://a.fi/wfs?api-key=salainen&x=1") == "https://a.fi/wfs"


def test_raakadata_tallennetaan_vain_muuttuessa(tmp_path: Path, tontti: gpd.GeoDataFrame) -> None:
    lahde = lahteet.Lahde(
        id="t",
        nimi="t",
        tyyppi="tiedosto",
        url="https://a.fi/x?api-key=salainen",
        epsg=3879,
        lisenssi="CC BY 4.0",
        attribuutio="Testi",
    )
    assert lahteet.tallenna_raaka(tontti, lahde, tmp_path) is not None
    assert lahteet.tallenna_raaka(tontti, lahde, tmp_path) is None
    meta = (tmp_path / "t" / "metatiedot.json").read_text(encoding="utf-8")
    assert "salainen" not in meta and "CC BY 4.0" in meta
