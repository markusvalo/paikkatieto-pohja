# Trendit ja alueelliset keskittymät

Menetelmät aikasarjojen muutoksen analysointiin säännöllisessä ruudukossa tai alueittain.
Toteutus on moduulissa `paikka.tilastot` (numpy, ei lisäriippuvuuksia), ja testit ovat tiedostossa
`tests/test_tilastot.py`. Menetelmät vastaavat eri kysymyksiin, joten niitä kannattaa käyttää rinnakkain.

## 0. Vertailukelpoisuus ensin
- **Puuttuva ei ole nolla.** Tilastoruudukoista jätetään usein pois pienet arvot tietosuojan vuoksi
  (esim. alle viiden asukkaan ruudut). Muutos lasketaan vain yksiköille, jotka ovat mukana kumpanakin
  vertailuvuotena. Kirjaa erikseen uudet, poistuneet ja vain välivuosina mukana olleet.
- **Rajaus ja luokitukset voivat muuttua** vuosien välillä (esim. mukaan otettavat kohteet tai
  käyttötarkoitusluokat). Valitse vertailuikkuna niin, ettei se ylitä muutosta, ja kirjaa syy.
- **Rajayksiköt:** jos yksikkö on osin tutkimusalueen ulkopuolella, muutos sisältää myös sen osan.
- **Normalisointi:** samankokoisissa ruuduissa absoluuttinen muutos on suoraan tiheyden muutos.
  Erikokoisilla alueilla muutos suhteutetaan pinta-alaan tai väestöön (CLAUDE.md, kartografia).

## 1. Absoluuttinen ja suhteellinen muutos
- Muutos = loppuvuosi − alkuvuosi.
- Prosenttimuutos lasketaan vain, kun lähtötaso ylittää alarajan (esim. 50 asukasta). Pienestä
  lähtötasosta prosentti on lähinnä kohinaa: 6 → 30 on +400 %.
- Vastaa kysymykseen: missä muutos on ollut määrällisesti suurin.

## 2. Trendi: Theil–Sen ja Mann–Kendall
- **Theil–Sen-kulmakerroin** (`theil_sen`) on kaikkien vuosiparien kulmakertoimien mediaani (Theil 1950,
  Sen 1968). Toisin kuin pienimmän neliösumman regressio, se kestää yksittäisiä poikkeavia vuosia,
  esimerkiksi rakennuksen valmistumisen hyppäyksen tai lähteen sijaintikorjauksen. Laske se vain
  yksiköille, jotka ovat mukana jokaisena vuotena (vähintään 3 vuotta).
- **Mann–Kendall** (`mann_kendall`) testaa monotonista trendiä (Mann 1945, Kendall 1975). τ on Kendallin
  tau-a väliltä −1…1, ja p on kaksisuuntainen normaaliapproksimaatiosta sidosten varianssikorjauksella
  ja jatkuvuuskorjauksella. Noin kymmenen vuoden sarjassa approksimaatio on kohtuullinen.
  Yksikkökohtaista p-arvoa ei ole korjattu moninkertaisen testauksen suhteen, joten se on
  johdonmukaisuuden mitta eikä löydös.
- Vastaa kysymykseen: onko muutos ollut tasaista vai yksittäinen hyppäys.

## 3. Alueelliset keskittymät: Getis–Ord Gi*
- **Gi\*** (`gi_tahti`) vertaa yksikön ja sen naapureiden arvojen summaa koko alueen jakaumaan (Getis &
  Ord 1992, Ord & Getis 1995). Yksikkö itse on mukana, ja painot ovat binääriset. Yksittäinen suuri
  muutos voi olla sattumaa, mutta Gi* löytää alueet, joilla suuret muutokset kasautuvat.
- **Naapuruus** (`ruutunaapurit`): kuningas eli 8 ympäröivää ruutua tai torni eli 4. Naapurit
  päätellään keskipisteistä ruudun koon mukaan, joten pienet poikkeamat keskipisteissä eivät haittaa.
  Yksiköt, joilla ei ole naapureita (saarekkeet), jäävät ilman arvoa.
- **Merkitsevyys:**
  - p-arvot lasketaan ehdollisella permutaatiolla (Anselin 1995): yksikön oma arvo pidetään, ja
    naapureiden arvot arvotaan muista. Muutokset ovat yleensä vinosti jakautuneita, joten
    normaaliapproksimaatio liioittelee löydöksiä (esimerkkiaineistossa 81 merkitsevää ruutua, kun
    permutaatio antoi 7).
  - Moninkertainen testaus (tuhansia yksiköitä) korjataan Benjamini–Hochbergin FDR-menetelmällä
    (`fdr_bh`, Benjamini & Hochberg 1995; paikallisissa tilastoissa de Castro & Singer 2006).
  - Permutaatioita tarvitaan vähintään 2 m / α (m = testien määrä), jotta pienin mahdollinen p-arvo
    jää FDR:n tiukimman rajan alle (`riittavat_permutaatiot`). Muuten mikään yksikkö ei voi olla
    merkitsevä, vaikka keskittymä olisi selvä.
  - Satunnaisluvut tulevat siemenestä, joka annetaan parametrina, joten tulokset ovat toistettavia.
- **Globaali Moranin I** (`morans_i`, Moran 1950) kertoo, onko muutos ylipäätään alueellisesti
  autokorreloitunutta. Raportoi se paikallisten keskittymien rinnalla.
- **Herkkyystarkastelu:** laske keskittymät myös toisella naapuruudella (esim. torni). Jos tulokset
  muuttuvat paljon, keskittymiä kannattaa pitää suuntaa antavina eikä tarkkoina rajoina.
- Vastaa kysymykseen: missä muutos on alueellisesti keskittynyttä.

## Tulkinta ja rajoitukset
- **MAUP** (Openshaw 1984): tulokset riippuvat yksikköjaosta. Toisella ruutukoolla tai aluejaolla
  keskittymät voivat näyttää erilaisilta.
- Gi* kertoo, missä arvot ovat poikkeuksellisia koko alueen jakaumaan nähden, ei syytä.
- Vierekkäiset, yhtä suuret vastakkaiset muutokset viittaavat usein lähteen sijaintikorjaukseen eivätkä
  todelliseen muutokseen. Tarkista ne ennen tulkintaa.
- Raportoi aina: vertailuikkuna, mukana olleiden yksiköiden määrä (uudet ja poistuneet), naapuruus,
  permutaatiot, FDR-taso, siemen sekä herkkyystarkastelun tulos.

## Lähteet
- Anselin, L. (1995). Local indicators of spatial association – LISA. *Geographical Analysis* 27(2), 93–115. https://doi.org/10.1111/j.1538-4632.1995.tb00338.x
- Benjamini, Y. & Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society B* 57(1), 289–300.
- de Castro, M. C. & Singer, B. H. (2006). Controlling the false discovery rate: a new application to account for multiple and dependent tests in local statistics of spatial association. *Geographical Analysis* 38(2), 180–208. https://doi.org/10.1111/j.0016-7363.2006.00682.x
- Getis, A. & Ord, J. K. (1992). The analysis of spatial association by use of distance statistics. *Geographical Analysis* 24(3), 189–206.
- Kendall, M. G. (1975). *Rank Correlation Methods*, 4. painos. London: Charles Griffin.
- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica* 13(3), 245–259.
- Moran, P. A. P. (1950). Notes on continuous stochastic phenomena. *Biometrika* 37(1/2), 17–23.
- Openshaw, S. (1984). *The Modifiable Areal Unit Problem*. CATMOG 38. Norwich: Geo Books.
- Ord, J. K. & Getis, A. (1995). Local spatial autocorrelation statistics: distributional issues and an application. *Geographical Analysis* 27(4), 286–306. https://doi.org/10.1111/j.1538-4632.1995.tb00912.x
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *Journal of the American Statistical Association* 63(324), 1379–1389.
- Theil, H. (1950). A rank-invariant method of linear and polynomial regression analysis I–III. *Proceedings of the Koninklijke Nederlandse Akademie van Wetenschappen* 53, 386–392, 521–525, 1397–1412.
