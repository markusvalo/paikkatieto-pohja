"""Komentorivi ilman verkkoa: polut työhakemistosta, ei paketin sijainnista (ADR 0004)."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

import paikka
from paikka import cli

JUURI = Path(__file__).resolve().parents[1]


def test_rekisteri_luetaan_tyohakemistosta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    (tmp_path / "config").mkdir()
    shutil.copy(JUURI / "config" / "lahteet.yaml", tmp_path / "config" / "lahteet.yaml")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["lahteet"]) == 0
    assert capsys.readouterr().out.strip()


def test_rekisteri_valitsimella(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--rekisteri", str(JUURI / "config" / "lahteet.yaml"), "lahteet"]) == 0
    assert capsys.readouterr().out.strip()


def test_puuttuva_rekisteri_kertoo_syyn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["lahteet"]) != 0
    assert "projektin juuresta" in caplog.text


def test_ei_polkuoletuksia_paketin_sijainnista() -> None:
    """Asennettuna paketti on site-packagesissa, joten sen sijainnista ei saa johtaa projektin polkuja."""
    for polku in (JUURI / "src" / "paikka").glob("*.py"):
        assert "__file__" not in polku.read_text(encoding="utf-8"), polku.name


def test_versio_pyprojectista() -> None:
    pyproject = tomllib.loads((JUURI / "pyproject.toml").read_text(encoding="utf-8"))
    assert paikka.__version__ == pyproject["project"]["version"]
