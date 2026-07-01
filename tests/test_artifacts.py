"""Tests for recipe-card artifact bundles and safe path handling."""

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from app.db.models import Card
from app.storage.artifacts import (
    BUNDLE_FILENAMES,
    create_job_bundle,
    resolve_card_artifacts,
    resolve_job_artifacts,
    write_metadata,
)


def _write_rendered_files(directory: Path) -> None:
    directory.mkdir(parents=True)
    (directory / "card.svg").write_text("<svg/>", encoding="utf-8")
    (directory / "card.png").write_bytes(b"png")
    (directory / "card.pdf").write_bytes(b"pdf")


def test_write_metadata_creates_stable_json(tmp_path: Path) -> None:
    """Metadata writing should create readable, deterministically ordered JSON."""
    paths = resolve_job_artifacts(tmp_path, 7)
    write_metadata(paths, {"title": "Soup", "card_id": 3})

    assert json.loads(paths.metadata.read_text(encoding="utf-8")) == {
        "card_id": 3,
        "title": "Soup",
    }
    assert paths.metadata.read_text(encoding="utf-8").index("card_id") < paths.metadata.read_text(
        encoding="utf-8"
    ).index("title")


def test_create_job_bundle_contains_every_required_file(tmp_path: Path) -> None:
    """Bundle creation should package rendered files and generated metadata."""
    paths = resolve_job_artifacts(tmp_path, 9)
    _write_rendered_files(paths.directory)

    bundle = create_job_bundle(
        tmp_path,
        "https://recipebot.example/cards/",
        job_id=9,
        card_id=4,
        title="Tomato Toast",
        slug="tomato-toast",
        source_url="https://reddit.com/r/recipes/comments/example",
    )

    assert bundle.paths.zip.is_file()
    assert bundle.urls["landing"] == "https://recipebot.example/cards/4"
    with ZipFile(bundle.paths.zip) as archive:
        assert archive.namelist() == list(BUNDLE_FILENAMES)
        metadata = json.loads(archive.read("metadata.json"))
    assert metadata["job_id"] == 9
    assert metadata["urls"]["zip"].endswith("/4/recipe-card.zip")


def test_create_job_bundle_requires_all_rendered_files(tmp_path: Path) -> None:
    """A bundle must not complete when a renderer output is absent."""
    paths = resolve_job_artifacts(tmp_path, 2)
    paths.directory.mkdir(parents=True)
    paths.svg.write_text("<svg/>", encoding="utf-8")
    paths.png.write_bytes(b"png")

    with pytest.raises(FileNotFoundError, match="card.pdf"):
        create_job_bundle(
            tmp_path,
            "http://localhost:8000/cards",
            job_id=2,
            card_id=2,
            title="Incomplete",
            slug="incomplete",
            source_url=None,
        )

    assert not paths.zip.exists()


def test_resolve_card_artifacts_rejects_path_outside_root(tmp_path: Path) -> None:
    """Stored database paths must never allow access outside ARTIFACT_ROOT."""
    outside = tmp_path.parent / "outside"
    card = Card(
        id=5,
        recipe_id=1,
        render_version="1",
        svg_path=str(outside / "card.svg"),
        png_path=str(outside / "card.png"),
        pdf_path=str(outside / "card.pdf"),
    )

    with pytest.raises(ValueError, match="escapes"):
        resolve_card_artifacts(tmp_path, 5, card)


def test_resolve_job_artifacts_rejects_nonpositive_id(tmp_path: Path) -> None:
    """Invalid numeric identifiers should not resolve to filesystem paths."""
    with pytest.raises(ValueError, match="positive"):
        resolve_job_artifacts(tmp_path, 0)
