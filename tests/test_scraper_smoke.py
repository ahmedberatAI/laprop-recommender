import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SCRAPER_SCRIPTS = [
    REPO_ROOT / "amazon_scraper.py",
    REPO_ROOT / "incehesap_scraper.py",
    REPO_ROOT / "vatan_scraper.py",
]


def _run_help(script: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=5,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


@pytest.mark.parametrize("script", SCRAPER_SCRIPTS)
def test_scraper_help(script: Path) -> None:
    if not script.exists():
        pytest.skip(f"Missing script: {script}")
    result = _run_help(script)
    assert result.returncode == 0, result.stderr[:500]


def test_incehesap_parse_list_fixture() -> None:
    from incehesap_scraper import InceHesapScraper, ScrapeConfig

    fixture_path = Path(__file__).parent / "fixtures" / "incehesap_list.html"
    html = fixture_path.read_text(encoding="utf-8")

    cfg = ScrapeConfig(base_categories=["https://www.incehesap.com/notebook/"])
    scraper = InceHesapScraper(cfg)
    data = scraper.parse_list_page_minimal(html, "https://www.incehesap.com/notebook/")

    assert data, "Expected at least one parsed product"
    # Validate a couple of fields for any entry
    sample = next(iter(data.values()))
    assert "url" in sample
    assert any("price" in row for row in data.values())
    assert any("name" in row for row in data.values())
