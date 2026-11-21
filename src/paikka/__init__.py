"""Paikkatietoprojektien yhteiset apuvälineet.

Moduulit:
    crs: koordinaattijärjestelmäprofiilit, muunnokset ja akselijärjestyksen tarkistus.
    merkisto: merkistöjen tunnistus, mojibake-korjaus, NFC-normalisointi, suomalainen lajittelu.
    tarkistus: aineiston laatutarkistukset (CRS, geometriat, alue, tekstit).
    tilastot: trendit (Theil–Sen, Mann–Kendall) ja keskittymät (Moranin I, Gi*, FDR) ilman lisäriippuvuuksia.
    lahteet: lähderekisteri (config/lahteet.yaml) ja haut OGC API Features-, WFS- (2.0, 1.0 / GML2)
        ja tiedostolähteistä.
    vienti: viennit GeoParquet-, GeoPackage-, GeoJSON-, Shapefile- ja Power BI -muotoihin.

Kirjasto jaetaan projekteihin versioituna pakettina tämän repon tageista (ADR 0004). Polut, kuten
lähderekisteri, annetaan argumentteina tai luetaan työhakemistosta; kirjasto ei oleta omaa sijaintiaan.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("paikka")  # pyproject.toml on ainoa versiolähde (ADR 0004)
except PackageNotFoundError:  # ajettu lähdekoodista asentamatta
    __version__ = "0+tuntematon"
