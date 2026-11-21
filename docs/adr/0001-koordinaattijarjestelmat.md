# ADR 0001: Koordinaattijärjestelmät

**Tila:** hyväksytty · **Päivämäärä:** 2026-11-17

## Konteksti

Työt ulottuvat yksittäisestä tontista koko Suomeen ja joskus Eurooppaan. Lähteet ovat
eri järjestelmissä: kunnat käyttävät GK-kaistoja, valtakunnalliset lähteet TM35FIN:ää ja
kansainväliset WGS84:ää tai LAEA:ta. Jakelukohteet (Power BI, verkkokartat) vaativat WGS84:n.

## Päätös

| Profiili | EPSG | Käyttö | Käyttöalue |
|---|---|---|---|
| `gk25` | 3879 | Pääkaupunkiseutu, tontti- ja korttelitaso | 24,5–25,5° E |
| `tm35` | 3067 | Koko Suomi, **oletus** | Suomi |
| `laea` | 3035 | Eurooppa-tason analyysi (tasapintainen) | Eurooppa |
| `wgs84` | 4326 | Jakelu: Power BI, GeoJSON, verkko | – |
| `web` | 3857 | Vain verkkotiilet | – |
| korkeus | 3900 | N2000-korkeudet | Suomi |

1. Analyysi tehdään aina metrisessä järjestelmässä. WGS84:ssä ja Web Mercatorissa ei
   lasketa pinta-aloja eikä etäisyyksiä.
2. Muunnos tehdään vasta, kun sitä tarvitaan. Esimerkiksi Helsingin aineisto pysyy
   GK25FIN:ssä koko analyysin ajan, ja WGS84-muunnos tehdään vasta vientivaiheessa.
3. Kun yhdistetään GK25FIN- ja TM35FIN-aineistoja, analyysijärjestelmä valitaan alueen
   mukaan: jos kaikki mahtuu GK25-kaistalle, GK25FIN, muuten TM35FIN.
   (`crs.ehdota_crs()`)
4. KKJ ja vanhat kuntien järjestelmät muunnetaan hakuvaiheessa. Jos lähde ei kerro
   järjestelmää, sitä ei arvata, vaan asia selvitetään lähteestä.

## Akselijärjestys

EPSG määrittelee järjestelmät 3879 (N, E), 3035 (Y, X) ja 4326 (lat, lon) pohjoinen edellä.
GeoPandas, Shapely ja QGIS käyttävät aina järjestystä x=itä, y=pohjoinen. WFS 2.0 ja
OGC API Features (`crs`-parametrilla) voivat palauttaa koordinaatit EPSG-järjestyksessä.

GK25FIN:ssä virhe näkyy selvästi, koska itäkoordinaatti alkaa kaistatunnuksella
(≈ 25 497 000) ja pohjoiskoordinaatti on ≈ 6 673 000. `crs.on_kayttoalueella()` ja
`crs.korjaa_akselit_tarvittaessa()` tunnistavat ja korjaavat vaihtuneet akselit. Käyttöalueen
tarkistuksessa sallitaan 20 km kaistan yli (`crs.KAYTTOALUE_TOLERANSSI_M`), koska GK-kaistoja käytetään
käytännössä hieman kaistan ulkopuolellakin. Vaihtuneet akselit poikkeavat miljoonia metrejä, joten
toleranssi ei heikennä niiden tunnistusta.

## Seuraukset

- Jokainen aineisto tarkistetaan (`paikka tarkista`) ennen analyysia ja vientiä.
- Lopputuotteissa koordinaatit pyöristetään metrisissä järjestelmissä 1 mm:iin ja
  WGS84:ssä 1e-7 asteeseen (≈ 1 cm). Power BI -viennissä käytetään 6 desimaalia (≈ 0,1 m).
