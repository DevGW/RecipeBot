"""Safe filesystem operations for rendered card artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from app.db.models import Card

RENDERED_FILENAMES = ("card.svg", "card.png", "card.pdf")
BUNDLE_FILENAMES = (*RENDERED_FILENAMES, "metadata.json")


@dataclass(frozen=True)
class ArtifactPaths:
    """Collect every file belonging to one completed recipe-card bundle."""

    directory: Path
    svg: Path
    png: Path
    pdf: Path
    metadata: Path
    zip: Path


@dataclass(frozen=True)
class ArtifactBundle:
    """Describe a validated local bundle and its public delivery URLs."""

    paths: ArtifactPaths
    urls: dict[str, str]


def resolve_job_artifacts(artifact_root: Path, job_id: int) -> ArtifactPaths:
    """Resolve canonical artifact paths for a positive job id."""
    if job_id < 1:
        raise ValueError("job_id must be a positive integer")
    root = artifact_root.expanduser().resolve()
    directory = (root / "jobs" / str(job_id)).resolve()
    _require_within_root(root, directory)
    return _paths_for_directory(directory)


def resolve_card_artifacts(artifact_root: Path, card_id: int, card: Card) -> ArtifactPaths:
    """Resolve and validate artifact paths stored for a specific card id."""
    if card.id != card_id:
        raise ValueError("card id does not match the loaded card")

    root = artifact_root.expanduser().resolve()
    stored_paths = {
        "card.svg": Path(card.svg_path).expanduser().resolve(),
        "card.png": Path(card.png_path).expanduser().resolve(),
        "card.pdf": Path(card.pdf_path).expanduser().resolve(),
    }
    for expected_name, stored_path in stored_paths.items():
        _require_within_root(root, stored_path)
        if stored_path.name != expected_name:
            raise ValueError(f"stored {expected_name} path has an unexpected filename")

    directories = {path.parent for path in stored_paths.values()}
    if len(directories) != 1:
        raise ValueError("stored card files must share one artifact directory")
    paths = _paths_for_directory(directories.pop())
    if (paths.svg, paths.png, paths.pdf) != (
        stored_paths["card.svg"],
        stored_paths["card.png"],
        stored_paths["card.pdf"],
    ):
        raise ValueError("stored card paths do not match the canonical artifact layout")
    return paths


def public_artifact_urls(artifact_base_url: str, card_id: int) -> dict[str, str]:
    """Build public landing and download URLs for one card."""
    base = artifact_base_url.rstrip("/")
    card_base = f"{base}/{card_id}"
    return {
        "landing": card_base,
        "png": f"{card_base}/card.png",
        "svg": f"{card_base}/card.svg",
        "pdf": f"{card_base}/card.pdf",
        "zip": f"{card_base}/recipe-card.zip",
    }


def write_metadata(paths: ArtifactPaths, metadata: dict[str, Any]) -> Path:
    """Write stable UTF-8 JSON metadata into an artifact directory."""
    paths.directory.mkdir(parents=True, exist_ok=True)
    paths.metadata.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return paths.metadata


def validate_bundle_inputs(paths: ArtifactPaths) -> None:
    """Raise an error unless every file required inside the ZIP exists."""
    missing = [
        filename
        for filename in BUNDLE_FILENAMES
        if not (paths.directory / filename).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"missing required artifact files: {', '.join(missing)}")


def create_zip_bundle(paths: ArtifactPaths) -> Path:
    """Create the downloadable ZIP after validating all required inputs."""
    validate_bundle_inputs(paths)
    temporary_path = paths.directory / "recipe-card.zip.tmp"
    with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED) as archive:
        for filename in BUNDLE_FILENAMES:
            archive.write(paths.directory / filename, arcname=filename)
    temporary_path.replace(paths.zip)
    if not paths.zip.is_file():
        raise RuntimeError("artifact bundle was not created")
    return paths.zip


def create_job_bundle(
    artifact_root: Path,
    artifact_base_url: str,
    *,
    job_id: int,
    card_id: int,
    title: str,
    slug: str,
    source_url: str | None,
) -> ArtifactBundle:
    """Write metadata and package the rendered outputs for a completed job."""
    paths = resolve_job_artifacts(artifact_root, job_id)
    urls = public_artifact_urls(artifact_base_url, card_id)
    metadata = {
        "card_id": card_id,
        "job_id": job_id,
        "slug": slug,
        "source_url": source_url,
        "title": title,
        "urls": urls,
    }
    write_metadata(paths, metadata)
    create_zip_bundle(paths)
    return ArtifactBundle(paths=paths, urls=urls)


def read_metadata(paths: ArtifactPaths) -> dict[str, Any]:
    """Read and decode metadata for a validated artifact directory."""
    try:
        data = json.loads(paths.metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("card metadata is unavailable or invalid") from error
    if not isinstance(data, dict):
        raise ValueError("card metadata must be a JSON object")
    return data


def _paths_for_directory(directory: Path) -> ArtifactPaths:
    return ArtifactPaths(
        directory=directory,
        svg=directory / "card.svg",
        png=directory / "card.png",
        pdf=directory / "card.pdf",
        metadata=directory / "metadata.json",
        zip=directory / "recipe-card.zip",
    )


def _require_within_root(root: Path, candidate: Path) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact path escapes ARTIFACT_ROOT") from error
