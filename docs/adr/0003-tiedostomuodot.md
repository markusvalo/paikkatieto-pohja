# ADR 0003: Tiedostomuodot ja jakelu

**Tila:** hyväksytty · **Päivämäärä:** 2026-11-17

## Päätös

| Vaihe | Muoto | Perustelu |
|---|---|---|
| Raakadata | GeoParquet + `metatiedot.json` | Nopea, tiivis, säilyttää CRS:n; metatiedoissa lähde, lisenssi ja tarkistussumma |
| Analyysi | GeoParquet, DuckDB Spatial | Koko Suomen aineistot ilman tietokantapalvelinta |
| Toimitus | GeoPackage | Toimii QGISissa, ArcGISissa ja FME:ssä, yksi tiedosto |
| Verkkokartta | PMTiles (tippecanoe) + MapLibre | Ei tiilipalvelinta, R2/Pages riittää |
| Power BI | CSV (lat/lon + WKT) | Toimii kartta- ja Azure Maps -visuaaleissa |
| Rasterit | Cloud Optimized GeoTIFF | Luettavissa URL:sta osissa |
| Shapefile | Vain jos vastaanottaja vaatii | 10 merkin kenttänimet, 2 Gt raja, merkistöongelmat |

Data säilytetään Gitin ulkopuolella. Julkiset lopputuotteet viedään Cloudflare R2:een
(ei siirtomaksuja), ja QGIS lukee ne suoraan URL:sta (`/vsicurl/`).

Muuta kuin avointa dataa ei viedä julkiseen bucketiin.
