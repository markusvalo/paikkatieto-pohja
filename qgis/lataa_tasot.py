"""Lataa julkaistut tasot QGISiin suoraan URL-osoitteista ja käytä repon tyylejä.

Käyttö (QGIS 3.44): Lisäosat → Python-konsoli → Näytä editori → Avaa tämä tiedosto → Suorita.
Tasot luetaan tiedostosta ``tasot.json`` tämän skriptin vieressä. Jos QGIS ei tunnista
skriptin sijaintia, aseta ASETUKSET-muuttujaan polku käsin.

Aineistoja ei ladata koneelle: QGIS lukee GeoParquetin ja COG:n URL:sta (GDAL /vsicurl/).
Kun julkaisuputki päivittää aineiston, seuraava avaus näyttää uuden version.
"""

import json
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)

ASETUKSET: Path | None = None  # esim. Path(r"C:\Projektit\paikkatieto-pohja\qgis\tasot.json")
LOKI = "Paikkatieto-pohja"


def _asetustiedosto() -> Path:
    if ASETUKSET is not None:
        return ASETUKSET
    try:
        return Path(__file__).resolve().with_name("tasot.json")
    except NameError as e:
        raise RuntimeError("Aseta ASETUKSET-muuttujaan tasot.json-tiedoston polku.") from e


def lataa() -> None:
    """Lue tasot.json ja lisää tasot nykyiseen projektiin."""
    polku = _asetustiedosto()
    asetukset = json.loads(polku.read_text(encoding="utf-8"))
    projekti = QgsProject.instance()
    projekti.setCrs(QgsCoordinateReferenceSystem(f"EPSG:{asetukset.get('projektin_epsg', 3067)}"))

    for taso in asetukset["tasot"]:
        lahde = taso["url"] if not taso["url"].startswith("http") else f"/vsicurl/{taso['url']}"
        if taso.get("tyyppi", "vektori") == "rasteri":
            kerros = QgsRasterLayer(lahde, taso["nimi"], "gdal")
        else:
            kerros = QgsVectorLayer(lahde, taso["nimi"], "ogr")
            kerros.setProviderEncoding("UTF-8")
        if not kerros.isValid():
            QgsMessageLog.logMessage(f"Tasoa ei voitu avata: {taso['nimi']} ({taso['url']})", LOKI, Qgis.Warning)
            continue
        if tyyli := taso.get("tyyli"):
            viesti, ok = kerros.loadNamedStyle(str(polku.parent / tyyli))
            if not ok:
                QgsMessageLog.logMessage(f"Tyyli epäonnistui ({tyyli}): {viesti}", LOKI, Qgis.Warning)
        projekti.addMapLayer(kerros)
        QgsMessageLog.logMessage(f"Lisätty: {taso['nimi']}", LOKI, Qgis.Info)


lataa()
