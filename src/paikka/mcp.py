"""Pieni MCP-asiakas (Model Context Protocol, Streamable HTTP) putkien hakuja varten.

Tukee vain sitä, mitä putket tarvitsevat: istunnon avaus (``initialize``), työkalun kutsu
(``tools/call``) ja vastaukset JSON- tai SSE-muodossa. Ei tunnistautumista: tunnuksia vaativia
palveluita ei käytetä tällä asiakkaalla.

Kohteliaisuus: kutsujen väliin jätetään vähintään ``vali_s`` sekuntia, ja ohimenevät virheet
(yhteys, 429, 5xx) yritetään uudelleen eksponentiaalisella odotuksella. Vanhentunut istunto
(HTTP 404) avataan kerran uudelleen.
"""

from __future__ import annotations

import itertools
import json
import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

import requests

from paikka import __version__

logger = logging.getLogger(__name__)

PROTOKOLLA = "2025-06-18"
AIKAKATKAISU_S = 120
YRITYKSET = 4
OHIMENEVAT = (429, 500, 502, 503, 504)


class McpVirhe(RuntimeError):
    """Palvelin palautti virheen (JSON-RPC-virhe tai työkalun ``isError``)."""


class _Istunto(Protocol):
    headers: Any

    def post(self, url: str, json: Any = ..., headers: dict[str, str] | None = ..., timeout: float = ...) -> Any: ...


def _jasenna(vastaus: requests.Response, pyynto_id: int) -> dict[str, Any]:
    """Poimi pyynnön vastausviesti JSON- tai SSE-rungosta."""
    tyyppi = vastaus.headers.get("Content-Type", "")
    if "text/event-stream" in tyyppi:
        viestit: list[dict[str, Any]] = []
        data: list[str] = []
        # SSE on aina UTF-8 (requests arvaisi ISO-8859-1:n), ja rivit erotetaan vain \n:llä:
        # str.splitlines() katkaisisi myös tekstin sisäisistä merkeistä (U+2028, U+0085).
        runko = vastaus.content.decode("utf-8")
        for rivi in [*runko.replace("\r\n", "\n").split("\n"), ""]:
            if rivi.startswith("data:"):
                data.append(rivi[5:].strip())
            elif not rivi.strip() and data:  # tapahtuman loppu
                viestit.append(json.loads("\n".join(data)))
                data = []
    else:
        runko = vastaus.json()
        viestit = runko if isinstance(runko, list) else [runko]
    for viesti in viestit:
        if viesti.get("id") == pyynto_id:
            if "error" in viesti:
                raise McpVirhe(f"JSON-RPC-virhe: {viesti['error']}")
            return viesti.get("result", {})
    raise McpVirhe(f"Vastauksessa ei ollut pyynnön {pyynto_id} tulosta.")


class Asiakas:
    """MCP-asiakas yhdelle palvelimelle.

    Args:
        url: Palvelimen MCP-osoite.
        istunto: HTTP-istunto (testeissä korvattavissa).
        vali_s: Vähimmäisväli kutsujen välillä sekunteina.
        nukkuja: Odotusfunktio (testeissä korvattavissa).
    """

    def __init__(
        self,
        url: str,
        istunto: _Istunto | None = None,
        vali_s: float = 1.0,
        nukkuja: Callable[[float], None] = time.sleep,
    ) -> None:
        self.url = url
        self.istunto = istunto or requests.Session()
        self.istunto.headers["User-Agent"] = f"paikka/{__version__} (+https://github.com/markusvalo/paikkatieto-pohja)"
        self.vali_s = vali_s
        self._nuku = nukkuja
        self._idt = itertools.count(1)
        self._istunto_id: str | None = None
        self._edellinen = 0.0
        self.kutsuja = 0

    def _otsakkeet(self) -> dict[str, str]:
        otsakkeet = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self._istunto_id:
            otsakkeet["Mcp-Session-Id"] = self._istunto_id
            otsakkeet["MCP-Protocol-Version"] = PROTOKOLLA
        return otsakkeet

    def _laheta(self, viesti: dict[str, Any]) -> requests.Response:
        """Lähetä viesti; ohimenevät virheet yritetään uudelleen."""
        odotus = max(0.0, self._edellinen + self.vali_s - time.monotonic())
        if odotus:
            self._nuku(odotus)
        for yritys in range(1, YRITYKSET + 1):
            try:
                vastaus = self.istunto.post(self.url, json=viesti, headers=self._otsakkeet(), timeout=AIKAKATKAISU_S)
            except (requests.ConnectionError, requests.Timeout) as e:
                if yritys == YRITYKSET:
                    raise McpVirhe(f"Yhteys palvelimeen {self.url} epäonnistui: {e}") from e
                logger.warning("Yhteysvirhe (%s), yritys %d/%d.", type(e).__name__, yritys, YRITYKSET)
            else:
                if vastaus.status_code not in OHIMENEVAT or yritys == YRITYKSET:
                    self._edellinen = time.monotonic()
                    return vastaus
                logger.warning("HTTP %d, yritys %d/%d.", vastaus.status_code, yritys, YRITYKSET)
            self._nuku(2.0**yritys)
        raise AssertionError("ei saavuteta")  # pragma: no cover

    def _tarkista(self, vastaus: requests.Response) -> None:
        if vastaus.status_code >= 400:
            selitys = (vastaus.text or "").strip().replace("\n", " ")[:300]
            raise McpVirhe(f"HTTP {vastaus.status_code} {self.url}: {selitys or '(ei selitystä)'}")

    def avaa(self) -> None:
        """Avaa istunto: ``initialize`` ja ``notifications/initialized``."""
        self._istunto_id = None
        pid = next(self._idt)
        vastaus = self._laheta(
            {
                "jsonrpc": "2.0",
                "id": pid,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOKOLLA,
                    "capabilities": {},
                    "clientInfo": {"name": "paikkatieto-pohja", "version": "0.5"},
                },
            }
        )
        self._tarkista(vastaus)
        tulos = _jasenna(vastaus, pid)
        self._istunto_id = vastaus.headers.get("Mcp-Session-Id")
        palvelin = tulos.get("serverInfo", {})
        logger.info("MCP-istunto avattu: %s %s", palvelin.get("name", "?"), palvelin.get("version", ""))
        self._tarkista(self._laheta({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def kutsu(self, tyokalu: str, argumentit: dict[str, Any]) -> list[str]:
        """Kutsu työkalua ja palauta sen tekstisisällöt.

        Raises:
            McpVirhe: Jos palvelin palauttaa virheen.
        """
        if self._istunto_id is None:
            self.avaa()
        for avattu_uudelleen in (False, True):
            pid = next(self._idt)
            viesti = {
                "jsonrpc": "2.0",
                "id": pid,
                "method": "tools/call",
                "params": {"name": tyokalu, "arguments": argumentit},
            }
            vastaus = self._laheta(viesti)
            if vastaus.status_code == 404 and not avattu_uudelleen:
                logger.info("MCP-istunto vanheni – avataan uudelleen.")
                self.avaa()
                continue
            self._tarkista(vastaus)
            self.kutsuja += 1
            tulos = _jasenna(vastaus, pid)
            tekstit = [c.get("text", "") for c in tulos.get("content", []) if c.get("type", "text") == "text"]
            if tulos.get("isError"):
                raise McpVirhe(f"Työkalu {tyokalu} palautti virheen: {' '.join(tekstit)[:300]}")
            return tekstit
        raise AssertionError("ei saavuteta")  # pragma: no cover
