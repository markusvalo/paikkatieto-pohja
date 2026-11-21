# V-000: Otsikko

**Tila:** luonnos | hyväksytty | toteutettu (vX.Y.Z) · **Issuet:** #
<!-- Tilaan merkitään, mitkä osat on toteutettu missäkin releasessa ja issuessa, esim.
     "aineisto A (#12) ja B (#14) toteutettu (v0.3.0) · C suunnitteilla (#15)". -->

## Tarve
Mitä haluan selvittää tai tuottaa, ja miksi?

## Aineistot
| Lähde (`config/lahteet.yaml`) | Taso tai kokoelma | Alue | Ajankohta | Lisenssi |
|---|---|---|---|---|

Lähteen erikoisuudet (puuttuvan arvon koodit, rajaukset, muuttuneet kentät, sivutus) kirjataan tähän
heti, kun ne havaitaan. Ne ovat seuraavan käyttäjän tärkein tieto.

## Paikkatietovaatimukset
- **Alue ja mittakaava:** tontti / kaupunginosa / kunta / Suomi / Eurooppa
- **Analyysin CRS:** EPSG:3879 / 3067 / 3035 (ADR 0001)
- **Tarkkuus:** esim. sijainti ±0,5 m, pinta-ala 1 m²
- **Tuotos:** GeoPackage (tasot ja sijainnittomat taulut) / pilvi (`<tuote>/`) / Power BI / kartta
- **Kieli:** suomi; desimaalipilkku ja tuhaterotin välilyönti esitysmuodoissa

## Käsittely ja menetelmät
Vaiheet järjestyksessä (haku → rajaus → muunnokset → johdetut kentät → tarkistus). Tilastollisille ja
spatiaalisille menetelmille: mitä mitataan, oletukset, parametrit (esim. naapuruus, permutaatiot,
merkitsevyystaso) ja tulkinta lähdeviitteineen. Herkkyystarkastelu, jos tulos riippuu valinnasta.

## Tuote
| Taso tai taulu | Rivi | Avain ja liitos | Keskeiset kentät |
|---|---|---|---|

## Hyväksymiskriteerit
Jokaisesta kriteeristä tehdään testi (`tests/`), kun se on mahdollista ilman verkkoa.
- [ ] 
- [ ] `paikka tarkista` ei löydä virheitä
- [ ] Lähdeattribuutiot näkyvät tuotoksessa (raportti tai metatiedot)
- [ ] Julkaisuajo on mennyt läpi, ja tuote on jakelussa

## Tulokset
**Koeajo PP.KK.VVVV** / **Julkaisuajo PP.KK.VVVV (dataversio `VVVV-KK-PP_HHMM`):** kohdemäärät, poikkeamat
ja havainnot. Seuraavissa ajoissa muutokset edelliseen selitetään.

## Rajaukset ja riskit
Henkilötiedot, lisenssien yhteensopivuus (esim. ODbL), aineiston ajantasaisuus, tunnetut virheet lähteessä.

## Lähteet
Aineistokuvaukset ja menetelmien viitteet linkkeineen.
