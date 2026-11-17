"""Paikkatietoprojektien yhteiset apuvälineet.

Moduulit:
    crs: koordinaattijärjestelmäprofiilit, muunnokset ja akselijärjestyksen tarkistus.
    merkisto: merkistöjen tunnistus, mojibake-korjaus, NFC-normalisointi, suomalainen lajittelu.
    tarkistus: aineiston laatutarkistukset (CRS, geometriat, alue, tekstit).
    lahteet: lähderekisteri (config/lahteet.yaml) ja haut OGC API Features-, WFS- ja tiedostolähteistä.
    vienti: viennit GeoParquet-, GeoPackage-, GeoJSON-, Shapefile- ja Power BI -muotoihin.
"""

__version__ = "0.1.0"
