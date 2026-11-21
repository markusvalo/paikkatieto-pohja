# Ohjeet tekoälyagentille

Tämä on paikkatietoprojektien pohja. Ylläpitäjä on maanmittari, ja työt ovat paikkatietoa,
karttoja, visualisointeja ja analyyseja julkisista lähteistä. Lopputuotteet ovat yleensä
suomeksi tai suomenkielisestä aineistosta.

## Ehdottomat säännöt

1. **Koordinaattijärjestelmä on aina tiedossa.** Älä koskaan arvaa tai aseta CRS:ää
   (`set_crs`) ilman lähteen dokumentaatiota. Muunna vain `paikka.crs.muunna()`-funktiolla.
2. **Sallitut järjestelmät** (ks. `docs/adr/0001-koordinaattijarjestelmat.md`):
   | Käyttö | Järjestelmä |
   |---|---|
   | Pääkaupunkiseutu, tontti- ja korttelitaso | ETRS-GK25FIN, **EPSG:3879** |
   | Koko Suomi, kunta- ja maakuntataso (oletus) | ETRS-TM35FIN, **EPSG:3067** |
   | Eurooppa-tason analyysi | ETRS89-LAEA, **EPSG:3035** |
   | Jakelu: Power BI, GeoJSON, verkko | WGS84, **EPSG:4326** |
   | Vain verkkotiilet | Web Mercator, EPSG:3857 |
   | Korkeudet | N2000, EPSG:3900 |
   - Pinta-alat, pituudet ja etäisyydet lasketaan **aina metrisessä** järjestelmässä,
     ei koskaan WGS84:ssä eikä Web Mercatorissa.
   - GK25FIN kattaa vain 24,5–25,5° itää. Jos aineisto ulottuu sen ulkopuolelle, käytä TM35FIN:ää.
   - KKJ- (EPSG:2391–2394, 3346) ja vanhat GK-kaistat muunnetaan heti hakuvaiheessa.
3. **Akselijärjestys:** koodissa aina x=itä/lon, y=pohjoinen/lat. EPSG:3879, 3035 ja 4326 ovat
   EPSG:n määritelmässä pohjoinen ensin, ja WFS 2.0 / OGC API (crs-parametri) voivat palauttaa
   ne niin. `lahteet.hae()` korjaa tämän automaattisesti; tarkista käsin haetut aineistot
   `crs.korjaa_akselit_tarvittaessa()`-funktiolla.
4. **Merkistö:** kaikki tiedostot UTF-8 ja NFC. Avaa tekstitiedostot aina `encoding="utf-8"`.
   Tuntemattomat tiedostot luetaan `merkisto.lue_teksti()`-funktiolla. CSV Exceliin ja
   Power BI:hin `merkisto.kirjoita_csv()` (UTF-8 BOM). Mojibakea (`Ã¤`, `Ã¶`) ei koskaan
   korjata hiljaa: se raportoidaan ja korjataan tietoisesti (`merkisto.korjaa_mojibake()`, tai jos arvoa ei voi
   palauttaa, `merkisto.tyhjenna_mojibake()`, joka palauttaa lokin raportoitavaksi).
5. **Suomalainen lajittelu:** `sorted(..., key=merkisto.suomi_lajitteluavain)` (å, ä, ö z:n jälkeen).
6. **Lisenssit:** jokainen lähde on kuvattu `config/lahteet.yaml`-tiedostossa lisenssin ja
   attribuution kanssa. Uutta lähdettä ei käytetä ennen kuin se on lisätty rekisteriin.
   OpenStreetMap (ODbL) sisältää jakamisvelvoitteen: ilmoita aina, jos sitä yhdistetään muuhun aineistoon.
7. **Henkilötiedot:** kiinteistöjen omistajatiedot, henkilöiden osoitteet ja tarkat
   sijaintihistoriat eivät kuulu tähän repoon. Aggregoi (ruudut, alueet) ennen julkaisua.
8. **Salaisuudet:** API-avaimet vain ympäristömuuttujista. Ei koskaan koodiin, lokiin tai metatietoihin.
9. **Raakadataa ei muokata.** `data/raw` → `data/processed` → `data/products`.
   Data ei kuulu Gitiin (ks. `.gitignore`).

## Mittakaavat

Tontista (~10 m, millimetritarkkuus) koko Suomeen (~1 200 km) ja joskus Eurooppaan.
- Tonttitasolla geometrioiden tarkkuus on olennainen: älä yksinkertaista, älä pyöristä analyysissä.
- Koko Suomen aineistoissa käytä GeoParquetia ja DuckDB Spatialia, ja rajaa bboxilla jo haussa.
- Lopputuotteissa koordinaatit pyöristetään: `crs.pyorista()` (1 mm / ~1 cm).
- Visualisoinnissa yleistä mittakaavan mukaan (tippecanoe hoitaa tiilet).

## Työnkulku

- Ympäristö: `pixi install`, testit `pixi run test`, linttaus `pixi run lint`.
- Komentorivi: `pixi run paikka --help`.
- Jokainen uusi analyysi tai putki saa testin. Testit eivät käytä verkkoa.
- Aineisto tarkistetaan aina ennen vientiä: `tarkistus.varmista(tarkistus.tarkista(gdf, ...))`.
- Vaatimukset: `docs/vaatimukset/`, arkkitehtuuripäätökset: `docs/adr/`, menetelmäkuvaukset: `docs/menetelmat/`.
- Uuden lähteen kokoelma, CRS-tuki ja kentät tarkistetaan ennen putken kirjoittamista: `pixi run paikka kokoelmat <lähde>`.
- Kiinteistötunnukset käsitellään `paikka.kiinteisto`-moduulilla (14 numeroa, esitysmuoto, laji), trendit ja
  keskittymät `paikka.tilastot`-moduulilla (menetelmät: `docs/menetelmat/trendit-ja-keskittymat.md`).
- `src/paikka` on versioitu kirjasto, jota projektit käyttävät git-tagilla (ADR 0004). Pidä se
  geneerisenä: ei projektikohtaisia arvoja eikä oletuksia repon hakemistorakenteesta.
- Commitit Conventional Commits -muodossa (`feat(lahteet): …`), rungossa *miksi*.

## Kartografia

- Värisokeille sopivat paletit (ColorBrewer, viridis). Ei punainen–vihreä-vastakkainasettelua.
- Jokaisessa kartassa on lähde- ja lisenssiattribuutio, mittakaava ja tarvittaessa pohjoisnuoli.
- Luokittelumenetelmä (luonnolliset luokat, kvantiilit, tasavälit) perustellaan.
- Teemakartoissa normalisoi (per asukas, per km²): absoluuttiset määrät koropleetteinä johtavat harhaan.
- Tekstit ja selitteet suomeksi, desimaalierotin pilkku, tuhaterotin välilyönti (1 234,5).
- QGIS-tyylit tallennetaan `qgis/tyylit/<aineisto>.qml`.

## Kun et ole varma

Kysy ennen kuin valitset koordinaattijärjestelmää, yhdistät eri lisenssien aineistoja tai
julkaiset mitään, mikä saattaa sisältää henkilötietoja.
