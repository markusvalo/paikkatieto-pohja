# Paikkatieto-pohja

Pohja paikkatietoprojekteille, joissa yhdistellään julkisia aineistoja ja tuotetaan analyyseja,
karttoja ja visualisointeja. Mittakaava ulottuu tontista koko Suomeen ja tarvittaessa
Eurooppaan. Tekoälyagentti (Claude Code, Copilot) tekee työn pilvessä, ja työkoneelta
tarvitaan vain QGIS ja selain.

```
Pilvi (Codespaces / Claude Code)           GitHub Actions                Työkone
──────────────────────────────            ───────────────────           ─────────────────
agentti kirjoittaa koodin,      ──push──▶  CI: testit + linttaus
testit, tyylit, skriptit                  julkaisu (ajastettu):
                                           haku → tarkistus → vienti  ──▶ R2 / Pages
                                           → PMTiles                       │
                                                                           ├──▶ QGIS 3.44 (URL)
                                                                           ├──▶ Power BI (CSV)
                                                                           └──▶ selain (MapLibre)
```

## Pikaopas

1. **Luo repo pohjasta.** Pura ZIP, luo GitHubiin uusi yksityinen repo ja vie tiedostot sinne
   (selaimessa: *Add file → Upload files*). Merkitse se halutessasi pohjaksi:
   *Settings → Template repository*.
2. **Avaa Codespace:** *Code → Codespaces → Create codespace on main*. Ympäristö
   (GDAL, GeoPandas, DuckDB, tippecanoe) asentuu automaattisesti, ja ensimmäinen kerta kestää muutaman minuutin.
3. **Varmista ympäristö:** `pixi run test`. Kaikkien testien pitää mennä läpi.
4. **Commitoi `pixi.lock`** ja vaihda CI:n `pixi install` → `pixi install --locked`.
5. **Tarkista lähteet** tiedostosta `config/lahteet.yaml`: esimerkkien URL-osoitteet ja
   tasonimet on tarkistettava ennen ensimmäistä ajoa.
6. **Salaisuudet** (*Settings → Secrets and variables → Actions*): `MML_API_KEY` ja
   tarvittaessa R2-tunnukset (ks. `.github/workflows/julkaisu.yml`).
7. Aja esimerkkiputki: `pixi run esimerkki`.

## Rakenne

```
CLAUDE.md                 Agentin säännöt: CRS, merkistöt, lisenssit, kartografia ← lue ensin
config/lahteet.yaml       Lähderekisteri: URL, CRS, lisenssi, attribuutio
src/paikka/               Python-paketti
  crs.py                  Profiilit (3879, 3067, 3035, 4326), muunnokset, akselitarkistus
  merkisto.py             UTF-8/cp1252-tunnistus, mojibake, NFC, suomalainen lajittelu, CSV
  tarkistus.py            Laatutarkistukset ennen analyysia ja vientiä
  lahteet.py              OGC API Features, WFS ja tiedostohaut sivutuksella
  vienti.py               GeoParquet, GeoPackage, GeoJSON, Shapefile, Power BI
putket/                   Ajettavat putket (esimerkki: Helsingin rakennukset)
tests/                    pytest, ei verkkoa
qgis/                     Tasojen lataus URL:sta, Processing-tarkistus, tyylit
web/index.html            MapLibre + PMTiles -katselin
docs/adr/                 Arkkitehtuuripäätökset (CRS, merkistöt, tiedostomuodot)
docs/vaatimukset/         Vaatimusmäärittelyt (pohja: _pohja.md)
data/raw → processed → products   (ei Gitiin)
```

## Komentorivi

```bash
pixi run paikka lahteet                                   # listaa lähderekisteri
pixi run paikka hae hki_rakennukset --rajaus 25496500 6673500 25497500 6674500
pixi run paikka tarkista aineisto.gpkg --alue suomi       # CRS, geometriat, ääkköset
pixi run paikka ehdota-crs aineisto.gpkg                  # gk25 / tm35 / laea laajuuden mukaan
pixi run paikka muunna aineisto.gpkg ulos.parquet --crs tm35
pixi run paikka vie ulos.parquet raportti.csv --muoto powerbi
```

## Koordinaattijärjestelmät lyhyesti

| | EPSG | Milloin |
|---|---|---|
| GK25FIN | 3879 | Pääkaupunkiseutu, tonttitaso |
| TM35FIN | 3067 | Koko Suomi, oletus |
| LAEA | 3035 | Eurooppa |
| WGS84 | 4326 | Vain jakelu: Power BI, GeoJSON, verkko |

Akselijärjestys korjataan automaattisesti, kun WFS tai OGC API palauttaa koordinaatit
järjestyksessä pohjoinen–itä. Tarkemmin: [ADR 0001](docs/adr/0001-koordinaattijarjestelmat.md).

## Merkistöt lyhyesti

UTF-8 ja NFC kaikkialla. CSV Power BI:hin ja Exceliin kirjoitetaan BOM:lla, jolloin ääkköset
toimivat. Vanhat cp1252-tiedostot tunnistetaan, ja mojibake (`Ã¤`) on tarkistuksessa virhe.
Tarkemmin: [ADR 0002](docs/adr/0002-merkistot.md).

## Power BI

`paikka vie … --muoto powerbi` tuottaa CSV:n, jossa on sarakkeet `lat` ja `lon` (WGS84,
6 desimaalia) sekä `wkt`. Alueille lat/lon on sisäpiste (point on surface), joka on aina
alueen sisällä toisin kuin keskipiste.

## Verkkokartta

`pixi run pmtiles` tuottaa tiedoston `data/products/tiilet.pmtiles`. Vie se ja
`web/index.html` samaan R2-bucketiin tai GitHub Pagesiin ja avaa
`index.html?pmtiles=<url>&nimi=Rakennukset&lahde=Helsingin+kaupunki`.

## Mainin suojaus (ruleset)

Tiedosto `.github/rulesets/main.json` sisältää säännöt oletushaaralle:

- Force push ja haaran poisto on estetty.
- Muutokset tulevat PR:n kautta. Hyväksyjää ei vaadita, joten sääntö toimii myös yksin työskennellessä.
- CI-tarkistuksen `testit` on mentävä läpi.
- Repon ylläpitäjä voi ohittaa säännöt hätätilanteessa.

Template ei kopioi asetuksia, joten ruleset tuodaan jokaiseen uuteen repoon erikseen:

1. Lataa `.github/rulesets/main.json` koneellesi (avaa tiedosto GitHubissa → *Download raw file*).
2. *Settings → Rules → Rulesets → New ruleset → Import a ruleset* → valitse tiedosto.
3. Tarkista säännöt ja paina *Create*.

GitHubin ilmaisella henkilötilillä rulesetit ovat voimassa vain julkisissa repoissa.

## Ennen ensimmäistä oikeaa projektia

- [ ] Valitse lisenssi koodille (esim. MIT) ja lisää `LICENSE`
- [ ] Tarkista työnantajan linjaukset tekoälypalveluista ja aineistojen viemisestä pilveen
- [ ] Tarkista lähteiden käyttöehdot, erityisesti kaupalliseen käyttöön ja ODbL-yhdistelmiin

## Tila

Python-paketti on testattu (47 testiä, ruff). Julkaisuputkea, QGIS-skriptejä, verkkokatselinta
ja `lahteet.yaml`-tiedoston URL-osoitteita ei ole ajettu oikeita palveluita vasten, joten
tarkista ne ensimmäisellä käyttökerralla.
