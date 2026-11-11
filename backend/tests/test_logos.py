import json

import pytest

from logo_credits import PNG, author, page, ship


def test_author_fields_publish_no_email_or_markup():
    assert author("Ada Example (<ada@example.org>), Example Foundation") == "Ada Example, Example Foundation"
    assert author('<a href="//x">Jane</a> jane@example.org') == "Jane"
    assert author("") == "see the file page"


def test_only_named_pngs_ship_and_logos_json_names_what_shipped(tmp_path):
    site, out = tmp_path / "site", tmp_path / "out"
    (site / "logos").mkdir(parents=True)
    out.mkdir()
    (site / "logos" / "0123456789abcdef.png").write_bytes(PNG + b"x")
    meta = {"source": {"name": "Wikimedia Commons"},
            "logos": {"Q1": "logos/0123456789abcdef.png", "Q2": "logos/fedcba9876543210.png", "Q3": "../secret.png"},
            "credits": {"Q1": ["A.png", "https://commons.wikimedia.org/wiki/File:A.png", "Ann <ann@example.org>", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0"],
                        "Q2": ["B.png", "https://commons.wikimedia.org/wiki/File:B.png", "Bo", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0"]}}
    (site / "logos.json").write_text(json.dumps(meta))
    kept, credits = ship(site, out)
    assert kept == {"Q1": "logos/0123456789abcdef.png"} and list(credits) == ["Q1"]   # a missing file or a strange path never ships
    assert json.loads((out / "logos.json").read_text())["logos"] == kept
    html = page(credits, {"Q1": "Acme"})
    assert "Acme" in html and "ann@example.org" not in html and "CC BY 4.0" in html


def test_a_file_that_is_not_a_png_stops_the_build(tmp_path):
    site, out = tmp_path / "site", tmp_path / "out"
    (site / "logos").mkdir(parents=True)
    out.mkdir()
    (site / "logos" / "0123456789abcdef.png").write_bytes(b"<svg onload=alert(1)>")
    (site / "logos.json").write_text(json.dumps({"source": {}, "logos": {"Q1": "logos/0123456789abcdef.png"}, "credits": {}}))
    with pytest.raises(SystemExit):
        ship(site, out)
