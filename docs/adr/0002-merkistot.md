# ADR 0002: Merkistöt ja suomenkielinen teksti

**Tila:** hyväksytty · **Päivämäärä:** 2026-11-17

## Konteksti

Aineistot ja tuotokset ovat suomeksi, ja niissä on ä, ö ja å. Vanhoissa lähteissä
(Shapefile ilman .cpg-tiedostoa, MapInfo, Excelistä tallennetut CSV:t) käytetään
Windows-1252- tai ISO-8859-1/-15-koodausta. Excel ja Power BI tulkitsevat UTF-8-CSV:n
oikein vain, jos tiedoston alussa on BOM. macOS tallentaa tiedostonimiä hajotetussa
muodossa (NFD), jolloin "ä" ei vastaa merkkiä "ä".

## Päätös

| Tilanne | Käytäntö |
|---|---|
| Kaikki tekstitiedostot | UTF-8, NFC, LF-rivinvaihdot |
| Tuntemattoman tiedoston luku | `merkisto.lue_teksti()`: kokeilee järjestyksessä UTF-8, cp1252, latin-1 ja varoittaa, jos tiedosto ei ole UTF-8 |
| CSV Power BI:hin | UTF-8 BOM, pilkku erottimena, piste desimaalina (`murre="powerbi"`) |
| CSV suomalaiseen Exceliin | UTF-8 BOM, puolipiste erottimena, pilkku desimaalina (`murre="excel_fi"`) |
| Shapefile (vain pakotettuna) | UTF-8 ja .cpg-tiedosto, ASCII-kenttänimet ≤ 10 merkkiä, muunnostaulukko mukaan |
| GeoPackage, GeoParquet, GeoJSON | UTF-8 määritelmän mukaan |
| Mojibake (`Ã¤`, `Ã¶`) | Tarkistus käsittelee sen virheenä. Korjaus tehdään tietoisesti `korjaa_mojibake()`-funktiolla, ei koskaan hiljaa. Jos arvoa ei voi palauttaa, `tyhjenna_mojibake()` tyhjentää sen ja palauttaa lokin raportoitavaksi |
| Lajittelu | `suomi_lajitteluavain()`: å, ä, ö z:n jälkeen |
| Python | `encoding="utf-8"` jokaisessa `open()`-kutsussa; Codespacesissa `PYTHONUTF8=1` |

## Seuraukset

- QGIS:ssä tason merkistöksi asetetaan UTF-8 (*Ominaisuudet → Lähde → Datan koodaus*),
  jos ääkköset näkyvät väärin vanhassa Shapefilessa.
- Sarakenimet tarkistetaan samoin kuin arvot.
