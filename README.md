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
  kiinteisto.py           Kiinteistötunnus (14 numeroa, esitysmuoto) ja kiinteistölaji
  merkisto.py             UTF-8/cp1252-tunnistus, mojibake, NFC, suomalainen lajittelu, CSV
  tarkistus.py            Laatutarkistukset ennen analyysia ja vientiä
  lahteet.py              OGC API Features, WFS (2.0 sivutuksella, 1.0 / GML2) ja tiedostohaut
  vienti.py               GeoParquet, GeoPackage, GeoJSON, Shapefile, Power BI
putket/                   Ajettavat putket (esimerkki: Helsingin rakennukset)
tests/                    pytest, ei verkkoa
qgis/                     Tasojen lataus URL:sta, Processing-tarkistus, tyylit
web/index.html            MapLibre + PMTiles -katselin
docs/adr/                 Arkkitehtuuripäätökset (CRS, merkistöt, tiedostomuodot, kirjaston jakelu)
docs/vaatimukset/         Vaatimusmäärittelyt (pohja: _pohja.md)
docs/release-tarkistuslista.md   Tarkistukset ennen jokaista releasea
data/raw → processed → products   (ei Gitiin)
```

## Komentorivi

```bash
pixi run paikka lahteet                                   # listaa lähderekisteri
pixi run paikka kokoelmat hki_rakennukset                 # onko taso palvelussa, CRS:t, kentät, vuodet
pixi run paikka hae hki_rakennukset --rajaus 25496500 6673500 25497500 6674500
pixi run paikka tarkista aineisto.gpkg --alue suomi       # CRS, geometriat, ääkköset
pixi run paikka ehdota-crs aineisto.gpkg                  # gk25 / tm35 / laea laajuuden mukaan
pixi run paikka muunna aineisto.gpkg ulos.parquet --crs tm35
pixi run paikka vie ulos.parquet raportti.csv --muoto powerbi
```

Vuosittain tai jaksoittain vaihtuvat tasonimet kirjataan rekisteriin paikkamerkillä, esim.
`kokoelma: "ns:Ruudukko_{vuosi}"`. Putki valitsee arvon palvelun tasoista ja täydentää lähteen:

```python
nimet = lahteet.tasonimet(lahteet.hae_capabilities(lahde))
lahde_2024 = lahteet.taydenna(lahde, vuosi=lahteet.vuodet(nimet, lahde.kokoelma)[-1])
```

Puolivuotisjaksoille (`12026`, `I_2024`, `20170811`) on `lahteet.uusin_jakso()`.

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
- CI-tarkistusten `testit` ja `paketti` on mentävä läpi.
- Repon ylläpitäjä voi ohittaa säännöt hätätilanteessa.

Template ei kopioi asetuksia, joten ruleset tuodaan jokaiseen uuteen repoon erikseen:

1. Lataa `.github/rulesets/main.json` koneellesi (avaa tiedosto GitHubissa → *Download raw file*).
2. *Settings → Rules → Rulesets → New ruleset → Import a ruleset* → valitse tiedosto.
3. Tarkista säännöt ja paina *Create*.

GitHubin ilmaisella henkilötilillä rulesetit ovat voimassa vain julkisissa repoissa.

## Kirjasto projekteissa

`src/paikka` on versioitu kirjasto ([ADR 0004](docs/adr/0004-kirjaston-jakelu.md)). Pohjasta luotu projekti
käyttää sitä riippuvuutena release-tagilla eikä pidä omaa kopiota:

1. `pixi.toml`:
   ```toml
   [pypi-dependencies]
   paikka = { git = "https://github.com/markusvalo/paikkatieto-pohja", tag = "v0.2.0" }
   ```
2. Poista projektista `src/paikka/`, kirjaston testit (`tests/test_crs.py`, `test_lahteet.py`,
   `test_merkisto.py`, `test_tarkistus.py`, `test_vienti.py`, `test_cli.py`) ja `pyproject.toml`:n
   `[build-system]`-, `[project]`- ja `[tool.hatch…]`-osiot. Projektiin jäävät putket, `config/`, tyylit ja
   dokumentaatio.
3. `pixi install` ja `pixi run test`.

**Päivitys:** vaihda tagi, aja `pixi install` ja testit, ja lue release notesista *Rikkovat muutokset*.
Komennot ajetaan projektin juuresta, koska lähderekisteri luetaan työhakemistosta (`config/lahteet.yaml`,
tai `paikka --rekisteri <polku>`). Versio: `paikka --versio`.

Yleishyödylliset parannukset tehdään tähän repoon ja tuodaan projektiin tagin vaihdolla. Projektissa voi
kokeilla ensin, mutta vakiintunut ratkaisu siirretään pohjaan issuena.

## Tehtävät ja releaset

Työ kulkee issuesta PR:ään ja releaseen:

1. **Issue** pohjalla *Tehtävä* (hyväksytty työ, milestone eli release) tai *Idea* (ei milestonea, ei toteuteta
   kesken muun työn). Virheet pohjalla *Bugi*.
2. **PR** omasta haarasta: rungossa `Closes #N`, sama milestone ja label kuin issuella (PR-pohja muistuttaa).
3. **Release:** milestonen viimeinen tehtävä on *Release-valmistelu vX.Y.Z* tarkistuslistan mukaan. Sen jälkeen
   ylläpitäjä tekee tagin ja GitHub Releasen; *Generate release notes* ryhmittelee PR:t labelien mukaan
   (`.github/release.yml`).

Labelien perussetti on tiedostossa `.github/labelit.yml`: `tehtävä`, `idea`, `bugi`, `rikkova`, `dokumentaatio`,
`infra`, `kirjasto` ja `qgis`. Projekti lisää omat tuotelabelinsa sekä listaan että release-kategorioihin.
Labelit luodaan tai päivitetään uuteen repoon kerralla (Codespacesissa tai missä `gh` on kirjautuneena):

```bash
python -c "import yaml,json;print(json.dumps(yaml.safe_load(open('.github/labelit.yml',encoding='utf-8'))))" \
  | jq -c '.[]' | while read -r l; do
      gh label create "$(jq -r .name <<<"$l")" --color "$(jq -r .color <<<"$l")" \
        --description "$(jq -r .description <<<"$l")" --force
    done
```

## Ennen ensimmäistä oikeaa projektia

- [ ] Valitse lisenssi koodille (esim. MIT) ja lisää `LICENSE`
- [ ] Tarkista työnantajan linjaukset tekoälypalveluista ja aineistojen viemisestä pilveen
- [ ] Tarkista lähteiden käyttöehdot, erityisesti kaupalliseen käyttöön ja ODbL-yhdistelmiin

## Tila

Python-paketti on testattu (pytest ja ruff, CI:ssä myös asennettuna pakettina). Julkaisuputkea, QGIS-skriptejä, verkkokatselinta
ja `lahteet.yaml`-tiedoston URL-osoitteita ei ole ajettu oikeita palveluita vasten, joten
tarkista ne ensimmäisellä käyttökerralla.
