"""GitHub-pohjat (.github/): issue-pohjat, release-kategoriat ja labelit pysyvät yhtenäisinä."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

GITHUB = Path(__file__).resolve().parents[1] / ".github"
LABELIT = {lab["name"]: lab for lab in yaml.safe_load((GITHUB / "labelit.yml").read_text(encoding="utf-8"))}


def test_labelit_ovat_kelvollisia() -> None:
    assert {"tehtävä", "idea", "bugi", "rikkova", "dokumentaatio", "infra"} <= set(LABELIT)
    for lab in LABELIT.values():
        assert len(str(lab["color"])) == 6 and int(str(lab["color"]), 16) >= 0
        assert lab["description"] and len(lab["description"]) <= 100  # GitHubin raja


@pytest.mark.parametrize("polku", sorted((GITHUB / "ISSUE_TEMPLATE").glob("*.yml")), ids=lambda p: p.name)
def test_issue_pohjat(polku: Path) -> None:
    pohja = yaml.safe_load(polku.read_text(encoding="utf-8"))
    if polku.name == "config.yml":
        return
    assert pohja["name"] and pohja["description"] and pohja["body"]
    assert set(pohja.get("labels", [])) <= set(LABELIT)


def test_release_kategoriat() -> None:
    asetukset = yaml.safe_load((GITHUB / "release.yml").read_text(encoding="utf-8"))["changelog"]
    kaytetyt = {lab for k in asetukset["categories"] for lab in k["labels"] if lab != "*"}
    assert kaytetyt <= set(LABELIT)
    assert asetukset["categories"][0]["labels"] == ["rikkova"]  # rikkovat muutokset ensin (ADR 0004)
    assert asetukset["categories"][-1]["labels"] == ["*"]
    assert "idea" in asetukset["exclude"]["labels"]


def test_pr_pohja() -> None:
    teksti = (GITHUB / "pull_request_template.md").read_text(encoding="utf-8")
    assert teksti.startswith("Closes #")
    assert "rikkova" in teksti
