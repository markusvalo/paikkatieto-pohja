# Release-tarkistuslista

Käytetään ennen jokaista releasea, sekä tässä pohjassa että pohjasta luoduissa projekteissa. Agentti
käy listan läpi milestonen viimeisenä tehtävänä, korjaa löydökset PR:ssä *Release-valmistelu vX.Y.Z*
(oma issue samassa milestonessa) ja raportoi, mitä tarkisti. Release on valmis vasta, kun PR on
yhdistetty ja CI on mennyt läpi; vasta sitten ylläpitäjä tekee tagin ja GitHub Releasen.

## 1. Milestone
- [ ] Kaikki milestonen issuet ja PR:t on suljettu. Keskeneräiset siirretään seuraavaan releaseen, eikä niitä jätetä roikkumaan.
- [ ] Uudet ideat ja sivuhavainnot on kirjattu issueiksi (`idea`, ei milestonea).
- [ ] Rikkovat muutokset on merkitty labelilla `rikkova`, jotta ne näkyvät release notesin alussa.

## 2. Dokumentaatio vastaa toteutusta
Jokainen tiedosto luetaan kokonaan ja verrataan toteutukseen, eikä tarkistus rajoitu muutettuihin kohtiin.

- [ ] **README.md**
  - pikaopas ja komennot toimivat sellaisinaan
  - rakenne, tuotteet (tila, kohdemäärät ja päivämäärä), ajot, tunnukset ja salaisuudet ovat ajan tasalla
  - vianetsintään on lisätty releasen aikana kohdatut virheet ratkaisuineen
  - *Tehtävät ja releaset* vastaa milestoneja
- [ ] **CLAUDE.md:** säännöt vastaavat nykyistä työtapaa ja rakennetta. Ristiriitaiset tai vanhentuneet ohjeet on poistettu.
- [ ] **docs/arkkitehtuuri.md** (jos on): kaaviot ja taulukot vastaavat nykyisiä osia, tietovirtoja, polkuja ja tunnuksia.
- [ ] **docs/adr/:** releasen aikana tehdyt arkkitehtuuripäätökset on kirjattu (uusi ADR tai päivitys). Vanhentuneet päätökset merkitään korvatuiksi, ei poisteta.
- [ ] **docs/vaatimukset/:** tila, hyväksymiskriteerit ja tulokset on päivitetty, ja poikkeamat ja riskit ovat ajan tasalla.
- [ ] **qgis/:** README, `tasot.json` ja tyylit kattavat uudet tasot ja polut.
- [ ] **config/lahteet.yaml:** käytössä olevat lähteet, lisenssit ja attribuutiot on kirjattu, ja kommentit ovat ajan tasalla.
- [ ] **Työnkulkujen, putkien ja moduulien otsakekommentit** vastaavat toimintaa.

## 3. Johdonmukaisuus
- [ ] Polut, tuote- ja tasonimet, EPSG-koodit ja asetusarvot (esim. säilytysaika) ovat samat dokumenteissa ja koodissa.
- [ ] Linkit ja viittaukset (ADR- ja issue-numerot, tiedostopolut) toimivat.
- [ ] Kieli on suomi, ääkköset ovat oikein, desimaalierotin on pilkku ja tuhaterotin välilyönti.

## 4. Kirjasto (pohjarepossa, ADR 0004)
- [ ] `pyproject.toml`:n `version` vastaa tulevaa tagia.
- [ ] Julkisen rajapinnan muutoksilla on testit, ja rikkovat muutokset on kuvattu PR:issä.
- [ ] README kertoo, millä tagilla projektit ottavat kirjaston käyttöön.

## 5. Data ja ajot (projekteissa, joissa on julkaisuputki)
- [ ] Julkaisuajo on ajettu tälle releaselle, ja jakelun työnkulut ovat menneet läpi.
- [ ] Kohdemäärät ja poikkeamalokit on tarkistettu, ja muutokset edelliseen releaseen on selitetty.

## 6. Raportti
Agentti kirjoittaa PR:ään yhteenvedon: mitkä tiedostot tarkistettiin, mitä muutettiin ja mitä jäi auki.
Ylläpitäjä yhdistää PR:n ja julkaisee releasen.
