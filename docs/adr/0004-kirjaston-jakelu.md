# ADR 0004: Kirjasto `paikka` jaetaan versioituna pakettina pohjarepon tageista

**Tila:** hyväksytty · **Päivämäärä:** 2026-11-21 · **Issue:** #5

## Konteksti
Pohjasta luodaan projekteja GitHubin *Use this template* -toiminnolla. Template-repo ei synkronoidu:
projekti saa pohjan sellaisena kuin se oli luontihetkellä, eikä pohjan myöhempiä korjauksia saa
projektiin ilman käsityötä. Toisin päin sama: projektissa tehty yleishyödyllinen jatkokehitys
(lähdetyypit, tilastot, pilvijulkaisu) jää projektiin, jos sitä ei kopioida pohjaan käsin.
Projektien määrän kasvaessa kopiot eriytyvät, ja sama korjaus pitää tehdä moneen paikkaan.

## Päätös
- **`src/paikka` on versioitu kirjasto**, jonka lähde on tämä repo. Pohja on siis sekä projektirunko
  että kirjaston koti; erillistä kirjastorepoa ei tehdä.
- **Projektit käyttävät kirjastoa riippuvuutena git-tagilla**, eivät kopiona:

  ```toml
  [pypi-dependencies]
  paikka = { git = "https://github.com/markusvalo/paikkatieto-pohja", tag = "v0.2.0" }
  ```

  Repo on julkinen, joten myös yksityinen projekti saa kirjaston ilman tunnuksia. Pohjan oma
  kehitysympäristö käyttää kirjastoa muokattavana (`path = "."`, `editable = true`).
- **Versiointi:** semanttinen (`vMAJOR.MINOR.PATCH`). Release-tagi on samalla kirjaston versio, ja
  `pyproject.toml`:n `version` päivitetään release-valmistelussa. Ennen v1.0.0:aa rikkova muutos
  kasvattaa MINOR-numeroa ja kirjataan release notesiin otsikolla *Rikkovat muutokset*.
- **Julkinen rajapinta** on `paikka`-paketin moduulien alaviivattomat funktiot, luokat ja vakiot sekä
  komentorivi `paikka`. Niillä on testit. Alaviivalliset nimet voivat muuttua milloin tahansa.
- **Yhteiset työnkulut uudelleenkäytettävinä** (v0.4.0 alkaen): projekti kutsuu pohjan työnkulkua
  tagilla, esim. `uses: markusvalo/paikkatieto-pohja/.github/workflows/vienti.yml@v0.4.0`, ja antaa
  projektikohtaiset arvot syötteinä ja salaisuuksina.
- **Projektiin jää vain projektikohtainen:** putket, `config/` (lähderekisteri, asetukset), tyylit,
  vaatimukset, projektin ADR:t ja dokumentaatio. Pohjasta luotu projekti poistaa oman `src/paikka`-
  kopionsa ja lisää riippuvuuden (README:n pikaopas).

## Hylätyt vaihtoehdot
- **Kopio pohjassa ja synkronointilista:** yksinkertaisin, mutta korjaukset kulkevat käsin ja
  unohtuvat, ja projektit eriytyvät. Tämä on nykytila, josta päätöksellä siirrytään pois.
- **Erillinen kirjastorepo:** selkeämpi raja, mutta kaksi repoa, kaksi CI:tä ja kaksi release-
  prosessia yhden ylläpitäjän työnä. Voidaan tehdä myöhemmin, jos pohja ja kirjasto alkavat
  kehittyä eri tahdissa.
- **PyPI- tai conda-forge-julkaisu:** turha omaan käyttöön; git-tagi riittää pixille.
- **Git-alimoduuli:** hankala päivittää ja helppo jättää vanhaksi, eikä ratkaise työnkulkuja.

## Seuraukset
- Kirjasto ei saa olettaa projektin hakemistorakennetta asennetun paketin sijainnista
  (`Path(__file__).parents[…]`). Polut, kuten lähderekisteri, annetaan argumenttina tai luetaan
  työhakemistosta. Nykyinen `cli.REKISTERI` korjataan v0.2.0:ssa.
- Projektikohtainen tieto (bucketin nimi, tuotteet, EPSG-oletus) tulee asetuksista, ei koodista.
- Yleishyödyllinen kehitys tehdään ensin pohjaan ja tuodaan projektiin tagin vaihdolla. Projektissa
  voi kokeilla ensin, mutta vakiintunut ratkaisu siirretään pohjaan issuena.
- Päivitys projektissa: vaihda tagi, aja testit. Rikkovat muutokset luetaan release notesista.
- Pohjan CI:n on testattava kirjasto myös asennettuna (ei vain muokattavana), jotta pakkauksesta
  puuttuvat tiedostot tai polkuoletukset huomataan.
