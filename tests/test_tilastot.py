"""Trendi- ja keskittymätilastot (paikka.tilastot) tunnetuilla aineistoilla."""

from __future__ import annotations

import numpy as np
import pytest

from paikka import tilastot as t


def test_theil_sen_kestaa_poikkeaman() -> None:
    x = np.arange(2015, 2026)
    y = 10.0 * (x - 2015)
    y[5] = 1000  # yksi poikkeava vuosi ei muuta mediaanikulmakerrointa
    assert t.theil_sen(x, y) == pytest.approx(10.0)
    with pytest.raises(ValueError):
        t.theil_sen([1, 1], [1, 2])


def test_mann_kendall() -> None:
    s, tau, p = t.mann_kendall(range(11))
    assert s == 55 and tau == 1.0 and p < 0.001
    s, tau, p = t.mann_kendall([5] * 11)  # pelkkiä sidoksia
    assert (s, tau, p) == (0.0, 0.0, 1.0)
    _, tau, p = t.mann_kendall([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5])
    assert abs(tau) < 0.5 and p > 0.05


def _ruudukko(n: int = 30) -> np.ndarray:
    xs, ys = np.meshgrid(np.arange(n), np.arange(n))
    # Tilastoruudukoiden keskipisteissä on usein sentin luokan poikkeamia ruudun keskeltä
    return np.c_[xs.ravel() * 250 + 25_470_125.0, ys.ravel() * 250 + 6_670_124.99]


def test_ruutunaapurit() -> None:
    k = _ruudukko(3)
    kuningas = t.ruutunaapurit(k, 250)
    torni = t.ruutunaapurit(k, 250, "torni")
    assert len(kuningas[4]) == 8 and len(torni[4]) == 4  # keskimmäinen ruutu
    assert len(kuningas[0]) == 3 and len(torni[0]) == 2  # kulma
    assert all(len(n) == 0 for n in t.ruutunaapurit(np.array([[125.0, 125.0], [1125.0, 1125.0]]), 250))
    with pytest.raises(ValueError):
        t.ruutunaapurit(k, 250, "lahetti")


def test_keskittyma_loytyy_ja_satunnainen_ei() -> None:
    k = _ruudukko()
    naapurit = t.ruutunaapurit(k, 250)
    rng = np.random.default_rng(1)
    satunnainen = rng.normal(0, 1, len(k))
    kulma = (k[:, 0] < 25_470_000 + 6 * 250) & (k[:, 1] < 6_670_000 + 6 * 250)
    keskittyma = satunnainen + 4 * kulma

    i, p = t.morans_i(keskittyma, naapurit)
    assert i > 0.2 and p <= 0.01
    z, pz = t.gi_tahti(keskittyma, naapurit, permutaatiot=9_999)
    merkitsevat = t.fdr_bh(pz)
    assert merkitsevat.sum() > 10
    assert (merkitsevat & kulma & (z > 0)).sum() / merkitsevat.sum() > 0.8

    _, ps = t.gi_tahti(satunnainen, naapurit, permutaatiot=9_999)
    assert t.fdr_bh(ps).sum() <= 2  # satunnaisessa ei juuri löydöksiä
    _, p_moran = t.morans_i(satunnainen, naapurit)
    assert p_moran > 0.01


def test_gi_tahti_saarekkeet_ja_vakio() -> None:
    z, p = t.gi_tahti([1.0, 2.0, 3.0], [np.array([1]), np.array([0]), np.array([], dtype=np.int64)], 99)
    assert np.isnan(z[2]) and np.isnan(p[2]) and not np.isnan(z[0])
    z, p = t.gi_tahti([2.0, 2.0, 2.0], [np.array([1]), np.array([0, 2]), np.array([1])], 99)
    assert np.isnan(z).all()


def test_fdr_bh() -> None:
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, np.nan])
    # Benjamini & Hochberg (1995) -esimerkin tapaan: rajat 0,05·k/m, m = 8 (NaN ei mukana)
    assert t.fdr_bh(p).tolist() == [True, True, False, False, False, False, False, False, False]
    assert not t.fdr_bh([np.nan]).any()


def test_riittavat_permutaatiot() -> None:
    assert t.riittavat_permutaatiot(100) == 9_999
    assert t.riittavat_permutaatiot(3_000, 0.05) == 120_000
    assert 1 / (t.riittavat_permutaatiot(3_000) + 1) < 0.05 / 3_000  # pienin p alle tiukimman FDR-rajan
    with pytest.raises(ValueError):
        t.riittavat_permutaatiot(0)
