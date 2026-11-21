"""MCP-asiakas (paikka.mcp) ilman verkkoa."""

from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from paikka import mcp


class _Vastaus:
    def __init__(self, viesti: dict[str, Any] | None, status: int = 200, sse: bool = True, istunto: str = "") -> None:
        self.status_code = status
        self.headers = {"Content-Type": "text/event-stream" if sse else "application/json"}
        if istunto:
            self.headers["Mcp-Session-Id"] = istunto
        teksti = "" if viesti is None else json.dumps(viesti, ensure_ascii=False)
        # Rivinvaihto merkkijonossa on JSONissa \n, mutta U+2028 ja U+0085 ovat raakoina (palvelin ei koodaa niitä).
        self.content = (f"event: message\ndata: {teksti}\n\n" if sse else teksti).encode("utf-8")
        self.text = self.content.decode("latin-1")  # requests arvaa SSE:lle väärän merkistön

    def json(self) -> Any:
        return json.loads(self.content)


class _Istunto:
    def __init__(self, vastaukset: list[Any]) -> None:
        self.vastaukset = vastaukset
        self.pyynnot: list[tuple[dict[str, Any], dict[str, str]]] = []
        self.headers: dict[str, str] = {}

    def post(self, url: str, json: Any = None, headers: dict[str, str] | None = None, timeout: float = 0) -> Any:
        self.pyynnot.append((json, dict(headers or {})))
        vastaus = self.vastaukset.pop(0)
        if isinstance(vastaus, Exception):
            raise vastaus
        if callable(vastaus):
            return vastaus(json)
        return vastaus


def _init(istunto: str = "abc") -> Any:
    return lambda viesti: _Vastaus(
        {"jsonrpc": "2.0", "id": viesti["id"], "result": {"serverInfo": {"name": "testi", "version": "1"}}},
        istunto=istunto,
    )


def _tulos(teksti: str, virhe: bool = False, sse: bool = True) -> Any:
    return lambda viesti: _Vastaus(
        {
            "jsonrpc": "2.0",
            "id": viesti["id"],
            "result": {"content": [{"type": "text", "text": teksti}], "isError": virhe},
        },
        sse=sse,
    )


def _asiakas(vastaukset: list[Any]) -> tuple[mcp.Asiakas, _Istunto, list[float]]:
    istunto = _Istunto(vastaukset)
    odotukset: list[float] = []
    return mcp.Asiakas("https://esim.fi/mcp/", istunto=istunto, vali_s=0, nukkuja=odotukset.append), istunto, odotukset


def test_istunto_avataan_ja_tunnus_valitetaan() -> None:
    asiakas, istunto, _ = _asiakas([_init("s1"), _Vastaus(None, status=202), _tulos("Käsite – ä\u2028ö")])
    assert asiakas.kutsu("haku", {"q": 1}) == ["Käsite – ä\u2028ö"]  # UTF-8 ja U+2028 säilyvät
    menetelmat = [p["method"] for p, _ in istunto.pyynnot]
    assert menetelmat == ["initialize", "notifications/initialized", "tools/call"]
    assert istunto.pyynnot[2][1]["Mcp-Session-Id"] == "s1"
    assert istunto.pyynnot[2][0]["params"] == {"name": "haku", "arguments": {"q": 1}}
    assert asiakas.kutsuja == 1


def test_json_vastaus_kelpaa() -> None:
    asiakas, _, _ = _asiakas([_init(), _Vastaus(None, status=202), _tulos("ok", sse=False)])
    assert asiakas.kutsu("haku", {}) == ["ok"]


def test_tyokalun_virhe_nostetaan() -> None:
    asiakas, _, _ = _asiakas([_init(), _Vastaus(None, status=202), _tulos("validation error", virhe=True)])
    with pytest.raises(mcp.McpVirhe, match="validation error"):
        asiakas.kutsu("haku", {})


def test_vanhentunut_istunto_avataan_uudelleen() -> None:
    asiakas, istunto, _ = _asiakas(
        [_init("s1"), _Vastaus(None, 202), _Vastaus(None, 404), _init("s2"), _Vastaus(None, 202), _tulos("ok")]
    )
    assert asiakas.kutsu("haku", {}) == ["ok"]
    assert istunto.pyynnot[-1][1]["Mcp-Session-Id"] == "s2"


def test_ohimenevat_virheet_yritetaan_uudelleen() -> None:
    asiakas, _, odotukset = _asiakas(
        [_init(), _Vastaus(None, 202), requests.ConnectionError("katkos"), _Vastaus(None, 503), _tulos("ok")]
    )
    assert asiakas.kutsu("haku", {}) == ["ok"]
    assert odotukset == [2.0, 4.0]


def test_pysyva_http_virhe() -> None:
    asiakas, _, _ = _asiakas([_init(), _Vastaus(None, 202), _Vastaus(None, 400, sse=False)])
    with pytest.raises(mcp.McpVirhe, match="HTTP 400"):
        asiakas.kutsu("haku", {})
