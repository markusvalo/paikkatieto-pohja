"""QGIS Processing -työkalu: tarkista tason koordinaattijärjestelmä, geometriat ja merkistö.

Samat periaatteet kuin Python-paketin ``paikka.tarkistus``-moduulissa, mutta toimii
suoraan QGISissa ilman asennuksia.

Asennus (QGIS 3.44): Processing-työkalut → Python-ikoni → Lisää skripti työkaluihin… →
valitse tämä tiedosto. Työkalu löytyy ryhmästä "Paikkatieto-pohja".
"""

from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
    QgsProcessingParameterFeatureSource,
)

SALLITUT = {"EPSG:3879", "EPSG:3067", "EPSG:3035", "EPSG:4326", "EPSG:3857"}
MOJIBAKE = ("Ã¤", "Ã¶", "Ã¥", "Ã„", "Ã–", "Ã…", "Ã©", "â€", "�")
# GK25FIN: itäkoordinaatti alkaa kaistatunnuksella 25.
GK25_ITA = (25_400_000, 25_600_000)
NAYTA_ENINTAAN = 5


class TarkistaAineisto(QgsProcessingAlgorithm):
    """Raportoi CRS-, geometria- ja merkistöongelmat."""

    INPUT = "INPUT"

    def name(self):
        return "tarkista_aineisto"

    def displayName(self):
        return "Tarkista aineisto (CRS, geometriat, merkistö)"

    def group(self):
        return "Paikkatieto-pohja"

    def groupId(self):
        return "paikkatieto_pohja"

    def shortHelpString(self):
        return (
            "Tarkistaa, että tason koordinaattijärjestelmä on sallittu (3879, 3067, 3035, 4326, 3857), "
            "GK25FIN-koordinaatit eivät ole väärin päin, geometriat ovat valideja eikä teksteissä ole "
            "rikkinäisiä ääkkösiä (mojibake, esim. 'Ã¤')."
        )

    def createInstance(self):
        return TarkistaAineisto()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.INPUT, "Syötetaso", [Qgis.ProcessingSourceType.VectorAnyGeometry])
        )
        self.addOutput(QgsProcessingOutputString("CRS", "Koordinaattijärjestelmä"))
        self.addOutput(QgsProcessingOutputNumber("VIRHEELLISET", "Virheelliset geometriat"))
        self.addOutput(QgsProcessingOutputNumber("TYHJAT", "Tyhjät geometriat"))
        self.addOutput(QgsProcessingOutputNumber("MOJIBAKE", "Rikkinäiset tekstiarvot"))

    def processAlgorithm(self, parameters, context, feedback):
        lahde = self.parameterAsSource(parameters, self.INPUT, context)
        authid = lahde.sourceCrs().authid()

        if authid not in SALLITUT:
            feedback.reportError(f"Koordinaattijärjestelmä {authid or 'puuttuu'} ei ole sallittu: {sorted(SALLITUT)}")
        if authid == "EPSG:3879":
            laajuus = lahde.sourceExtent()
            if not (GK25_ITA[0] <= laajuus.xMinimum() and laajuus.xMaximum() <= GK25_ITA[1]):
                feedback.reportError(
                    "GK25FIN-koordinaatit näyttävät olevan väärin päin (x:n pitäisi olla ~25 500 000). "
                    "Tarkista lähteen akselijärjestys."
                )

        for kentta in lahde.fields():
            if any(m in kentta.name() for m in MOJIBAKE):
                feedback.reportError(f"Rikkinäinen kenttänimi: {kentta.name()!r}")

        yhteensa = lahde.featureCount() or 1
        virheelliset = tyhjat = mojibake = 0
        for i, kohde in enumerate(lahde.getFeatures()):
            if feedback.isCanceled():
                break
            geometria = kohde.geometry()
            if geometria.isNull() or geometria.isEmpty():
                tyhjat += 1
            elif not geometria.isGeosValid():
                virheelliset += 1
                if virheelliset <= NAYTA_ENINTAAN:
                    feedback.pushWarning(f"Virheellinen geometria: kohde {kohde.id()}")
            for arvo in kohde.attributes():
                if isinstance(arvo, str) and any(m in arvo for m in MOJIBAKE):
                    mojibake += 1
                    if mojibake <= NAYTA_ENINTAAN:
                        feedback.pushWarning(f"Rikkinäinen teksti kohteessa {kohde.id()}: {arvo[:60]!r}")
            feedback.setProgress(int(100 * (i + 1) / yhteensa))

        feedback.pushInfo(
            f"CRS: {authid} | virheellisiä geometrioita: {virheelliset} | tyhjiä: {tyhjat} | "
            f"rikkinäisiä tekstejä: {mojibake}"
        )
        if virheelliset:
            feedback.pushInfo("Korjaa: Vektori → Geometriatyökalut → Korjaa geometriat.")
        if mojibake:
            feedback.pushInfo("Kokeile: Ominaisuudet → Lähde → Datan koodaus = UTF-8 tai Windows-1252.")
        return {"CRS": authid, "VIRHEELLISET": virheelliset, "TYHJAT": tyhjat, "MOJIBAKE": mojibake}
