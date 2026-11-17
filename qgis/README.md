# QGIS-tiedostot

Nämä toimivat työkoneen QGIS 3.44:ssä ilman lisäasennuksia.

| Tiedosto | Mitä se tekee |
|---|---|
| `lataa_tasot.py` | Lisää julkaistut tasot projektiin suoraan URL:sta ja käyttää repon tyylejä. Asetukset ovat tiedostossa `tasot.json`. |
| `processing/tarkista_aineisto.py` | Processing-työkalu, joka tarkistaa CRS:n, GK25-akselit, geometriat ja ääkköset. |
| `tyylit/*.qml` | Tasojen tyylit. Tallenna QGISissa: *Tason ominaisuudet → Tyyli → Tallenna tyyli → QGIS-tasotyylitiedosto*. |
| `mallit/*.model3` | Processing-mallit (graafinen mallintaja). |

## Työnkulku tekoälyagentin kanssa

1. Agentti (Codespaces tai Claude Code verkossa) kirjoittaa tyylin, mallin tai PyQGIS-skriptin tähän kansioon.
2. Lataat repon ZIP-tiedostona (*Code → Download ZIP*) tai pelkän tiedoston GitHubista.
3. Avaat tiedoston QGISissa. Jos skripti kaatuu, liitä virheilmoitus (*Näytä → Paneelit →
   Lokiviestit*) agentille.
4. Kun tyyli on viimeistelty QGISissa, tallenna se `.qml`-tiedostoksi ja vie takaisin repoon.
   Näin agentti näkee muutoksesi.

## Huomioita

- `/vsicurl/` toimii vain julkisille URL-osoitteille. Muuta kuin avointa dataa ei pidä
  viedä julkiseen bucketiin.
- Jos ääkköset näkyvät väärin vanhassa Shapefilessa: *Ominaisuudet → Lähde → Datan
  koodaus*. Kokeile ensin UTF-8 ja sitten Windows-1252.
- Skriptejä ei ole ajettu QGISissa ennen julkaisua. Python-paketin testit eivät kata niitä.
