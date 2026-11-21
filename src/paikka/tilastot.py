"""Trendi- ja alueellisen autokorrelaation tilastot ilman lisäriippuvuuksia (numpy).

Menetelmät, tulkinta ja lähteet: docs/menetelmat/trendit-ja-keskittymat.md.

    theil_sen       Theil (1950), Sen (1968): parittaisten kulmakertoimien mediaani
    mann_kendall    Mann (1945), Kendall (1975): monotonisen trendin testi, sidosten korjaus
    ruutunaapurit   kuningas- (8) tai tornisuhde (4) säännöllisessä ruudukossa
    morans_i        globaali Moranin I, rivistandardoitu W, permutaatio-p (Anselin 1995)
    gi_tahti        Getis–Ord Gi* (Getis & Ord 1992, Ord & Getis 1995), z ja ehdollinen permutaatio-p
    fdr_bh          Benjamini & Hochberg (1995): väärien löydösten osuuden korjaus
    riittavat_permutaatiot  permutaatioiden määrä, jolla FDR voi löytää merkitseviä

Satunnaislukujen siemen annetaan parametrina, jotta tulokset ovat toistettavia.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike

PERMUTAATIOT = 999
SIEMEN = 20261118  # oletussiemen; anna oma parametrina toistettavuuden vuoksi


def theil_sen(x: ArrayLike, y: ArrayLike) -> float:
    """Theil–Sen-kulmakerroin: kaikkien pisteparien kulmakertoimien mediaani.

    Raises:
        ValueError: Jos pisteitä on alle kaksi tai kaikki x-arvot ovat samat.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    ok = dx != 0
    if not ok.any():
        raise ValueError("Theil–Sen vaatii vähintään kaksi eri x-arvoa.")
    return float(np.median((y[j] - y[i])[ok] / dx[ok]))


def normaali_p(z: float | np.ndarray) -> float | np.ndarray:
    """Kaksisuuntainen p normaalijakaumasta."""
    return np.vectorize(lambda v: math.erfc(abs(v) / math.sqrt(2)))(z)


def mann_kendall(y: Sequence[float]) -> tuple[float, float, float]:
    """Mann–Kendallin trenditesti aikajärjestyksessä oleville arvoille.

    Returns:
        (S, Kendallin tau, kaksisuuntainen p). p normaaliapproksimaatiosta jatkuvuuskorjauksella ja
        sidosten varianssikorjauksella (Kendall 1975). Pienillä n (< 10) p on suuntaa antava.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    i, j = np.triu_indices(n, k=1)
    s = float(np.sign(y[j] - y[i]).sum())
    _, toistot = np.unique(y, return_counts=True)
    varianssi = (n * (n - 1) * (2 * n + 5) - float((toistot * (toistot - 1) * (2 * toistot + 5)).sum())) / 18
    if varianssi <= 0:
        return s, 0.0, 1.0
    z = (s - np.sign(s)) / math.sqrt(varianssi) if s != 0 else 0.0
    tau = s / (n * (n - 1) / 2)
    return s, float(tau), float(normaali_p(z))


def ruutunaapurit(keskipisteet: np.ndarray, koko: float, suhde: str = "kuningas") -> list[np.ndarray]:
    """Naapuri-indeksit säännöllisessä ruudukossa keskipisteiden perusteella (ei itseä).

    Args:
        keskipisteet: (n, 2) x, y.
        koko: ruudun sivu (m).
        suhde: "kuningas" (8 naapuria, myös kulmat) tai "torni" (4, vain sivut).
    """
    rivi = np.floor(keskipisteet[:, 1] / koko).astype(np.int64)  # keskipiste on ruudun sisällä
    sarake = np.floor(keskipisteet[:, 0] / koko).astype(np.int64)
    paikka = {(r, s): k for k, (r, s) in enumerate(zip(rivi, sarake, strict=True))}
    siirrot = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if suhde == "kuningas":
        siirrot += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    elif suhde != "torni":
        raise ValueError(f"Tuntematon naapuruussuhde {suhde!r}.")
    return [
        np.array([paikka[(r + dr, s + ds)] for dr, ds in siirrot if (r + dr, s + ds) in paikka], dtype=np.int64)
        for r, s in zip(rivi, sarake, strict=True)
    ]


def _reunat(naapurit: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Naapuruuslistat reunoiksi (rivi, sarake) ja naapurien määrät."""
    maarat = np.array([len(n) for n in naapurit], dtype=np.int64)
    rivit = np.repeat(np.arange(len(naapurit)), maarat)
    sarakkeet = np.concatenate(naapurit) if len(rivit) else np.array([], dtype=np.int64)
    return rivit, sarakkeet, maarat


def morans_i(
    x: ArrayLike, naapurit: list[np.ndarray], permutaatiot: int = PERMUTAATIOT, siemen: int = SIEMEN
) -> tuple[float, float]:
    """Globaali Moranin I rivistandardoidulla W:llä ja permutaatio-p (yksisuuntainen, positiivinen).

    Saarekkeet (ei naapureita) jätetään pois.
    """
    x = np.asarray(x, dtype=float)
    rivit, sarakkeet, maarat = _reunat(naapurit)
    mukana = maarat > 0

    def arvo(v: np.ndarray) -> float:
        z = v - v.mean()
        viive = np.bincount(rivit, weights=z[sarakkeet], minlength=len(v)).astype(float)
        viive[mukana] /= maarat[mukana]
        return float((z[mukana] * viive[mukana]).sum() / (z[mukana] ** 2).sum())

    if not mukana.any() or np.allclose(x, x.mean()):
        return float("nan"), 1.0
    havaittu = arvo(x)
    rng = np.random.default_rng(siemen)
    suuremmat = sum(arvo(rng.permutation(x)) >= havaittu for _ in range(permutaatiot))
    return havaittu, (suuremmat + 1) / (permutaatiot + 1)


def gi_tahti(
    x: ArrayLike, naapurit: list[np.ndarray], permutaatiot: int = PERMUTAATIOT, siemen: int = SIEMEN
) -> tuple[np.ndarray, np.ndarray]:
    """Getis–Ord Gi* (binääripainot, ruutu itse mukana) ja ehdollinen permutaatio-p (kaksisuuntainen).

    Ehdollisessa permutaatiossa ruudun oma arvo pidetään ja naapurit arvotaan muista ruuduista
    (Anselin 1995). Otanta tehdään palauttaen: naapureita on enintään 8 ja ruutuja tuhansia, joten
    ero otantaan ilman palautusta on merkityksetön, ja laskenta vektoroituu.

    Returns:
        (z, p). Saarekkeille (ei naapureita) NaN.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    keskiarvo = x.mean()
    s = math.sqrt(max((x**2).mean() - keskiarvo**2, 0.0))
    z = np.full(n, np.nan)
    p = np.full(n, np.nan)
    if n < 3 or s == 0:
        return z, p
    rng = np.random.default_rng(siemen)
    for i, naap in enumerate(naapurit):
        k = len(naap)
        if k == 0:
            continue
        w = k + 1
        nimittaja = s * math.sqrt((n * w - w**2) / (n - 1))
        z[i] = (x[naap].sum() + x[i] - keskiarvo * w) / nimittaja
        otos = rng.integers(0, n - 1, size=(permutaatiot, k))
        otos += otos >= i  # ohita ruutu itse
        z_perm = (x[otos].sum(axis=1) + x[i] - keskiarvo * w) / nimittaja
        p[i] = ((np.abs(z_perm) >= abs(z[i])).sum() + 1) / (permutaatiot + 1)
    return z, p


def fdr_bh(p: ArrayLike, alfa: float = 0.05) -> np.ndarray:
    """Benjamini–Hochberg: totuusarvo, onko löydös merkitsevä FDR-tasolla alfa. NaN = ei merkitsevä."""
    p = np.asarray(p, dtype=float)
    tulos = np.zeros(len(p), dtype=bool)
    ok = ~np.isnan(p)
    arvot = p[ok]
    m = len(arvot)
    if m == 0:
        return tulos
    jarjestys = np.argsort(arvot)
    rajat = alfa * np.arange(1, m + 1) / m
    alle = arvot[jarjestys] <= rajat
    if alle.any():
        k = np.max(np.nonzero(alle)[0])
        merkitsevat = np.zeros(m, dtype=bool)
        merkitsevat[jarjestys[: k + 1]] = True
        tulos[np.nonzero(ok)[0]] = merkitsevat
    return tulos


def riittavat_permutaatiot(testeja: int, alfa: float = 0.05, vahintaan: int = 9_999) -> int:
    """Permutaatioiden määrä paikallisille testeille, joiden p-arvot korjataan FDR:llä.

    Permutaatio-p:n pienin mahdollinen arvo on 1 / (P + 1). Sen on oltava selvästi alle FDR:n tiukimman
    rajan alfa / m, muuten mikään testi ei voi olla merkitsevä. Siksi P ≥ 2 m / alfa.

    Raises:
        ValueError: Jos testejä ei ole tai alfa ei ole väliltä (0, 1).
    """
    if testeja < 1 or not 0 < alfa < 1:
        raise ValueError("Testejä on oltava vähintään yksi ja alfan väliltä (0, 1).")
    return max(vahintaan, math.ceil(2 * testeja / alfa))
