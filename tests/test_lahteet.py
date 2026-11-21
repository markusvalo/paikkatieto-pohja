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


def test_http_virhe_ei_paljasta_avainta(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    monkeypatch.setenv("TESTI_AVAIN", "  salainen\n")  # liitetty rivinvaihdon kanssa
    vastaus = requests.Response()
    vastaus.status_code = 403
    vastaus.url = "https://esim.fi/collections/x/items?api-key=salainen"
    vastaus._content = b'{"message": "Invalid API key"}'

    class _Istunto:
        params: dict[str, Any] | None = None

        def get(self, url: str, params: dict[str, Any] | None = None, timeout: float = 0) -> requests.Response:
            self.params = params
            return vastaus

    istunto = _Istunto()
    lahde = lahteet.Lahde(
        id="x",
        nimi="x",
        tyyppi="ogc_api_features",
        url="https://esim.fi",
        kokoelma="x",
        epsg=3067,
        lisenssi="x",
        attribuutio="x",
        api_avain_env="TESTI_AVAIN",
    )
    with pytest.raises(RuntimeError) as virhe:
        lahteet.hae(lahde, istunto=istunto)
    viesti = str(virhe.value)
    assert "salainen" not in viesti
    assert "403" in viesti and "Invalid API key" in viesti
    assert virhe.value.__cause__ is None and virhe.value.__suppress_context__
    assert istunto.params["api-key"] == "salainen"  # välilyönnit ja rivinvaihto poistettu


def test_kohteen_id_sailyy() -> None:
    lahde = lahteet.Lahde(
        id="t",
        nimi="t",
        tyyppi="ogc_api_features",
        url="https://esim.fi",
        kokoelma="k",
        epsg=3067,
        lisenssi="x",
        attribuutio="x",
    )
    kohde = {**_kohde(385_000, 6_672_000, "A"), "id": "123"}
    ilman_ominaisuuksia = {
        "type": "Feature",
        "id": "124",
        "properties": None,
        "geometry": {"type": "Point", "coordinates": [385_001, 6_672_001]},
    }
    gdf = lahteet.hae(lahde, istunto=_ValeIstunto([{"features": [kohde, ilman_ominaisuuksia], "links": []}]))
    assert list(gdf["kohde_id"]) == ["123", "124"]


def test_epsg_pakollinen_paitsi_sijainnittomilla(tmp_path: Path) -> None:
    rekisteri = tmp_path / "lahteet.yaml"
    yhteiset = "lisenssi: x\n    attribuutio: x\n    url: https://esim.fi"
    rekisteri.write_text(f"lahteet:\n  arkisto:\n    nimi: a\n    tyyppi: mcp\n    {yhteiset}\n", encoding="utf-8")
    assert lahteet.lataa_rekisteri(rekisteri)["arkisto"].epsg is None
    rekisteri.write_text(f"lahteet:\n  w:\n    nimi: w\n    tyyppi: wfs\n    {yhteiset}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="puuttuu epsg"):
        lahteet.lataa_rekisteri(rekisteri)


@pytest.mark.parametrize(("tyyppi", "epsg", "viesti"), [("mcp", None, "MCP"), ("wms", 3879, "WMS")])
def test_ei_haettavat_lahteet(tyyppi: str, epsg: int | None, viesti: str) -> None:
    lahde = lahteet.Lahde(
        id="x", nimi="x", tyyppi=tyyppi, url="https://esim.fi", epsg=epsg, lisenssi="x", attribuutio="x"
    )
    with pytest.raises(ValueError, match=viesti):
        lahteet.hae(lahde, istunto=_ValeIstunto([]))


def test_lisaparametrit_valitetaan_wfs_hakuun() -> None:
    import requests

    class _Istunto:
        params: dict[str, Any] | None = None

        def get(self, url: str, params: dict[str, Any] | None = None, timeout: float = 0) -> requests.Response:
            self.params = dict(params or {})
            r = requests.Response()
            r.status_code = 200
            r._content = b'{"features": []}'
            return r

    istunto = _Istunto()
    lahde = lahteet.Lahde(
        id="w",
        nimi="w",
        tyyppi="wfs",
        url="https://esim.fi/wfs",
        kokoelma="t",
        epsg=3879,
        lisenssi="x",
        attribuutio="x",
        lisaparametrit={"sortBy": "id", "cql_filter": "kunta='091'"},
    )
    lahteet.hae(lahde, istunto=istunto)
    assert istunto.params["sortBy"] == "id" and istunto.params["cql_filter"] == "kunta='091'"
