"""Shared plumbing for the quarterly-deck scripts: paths, brand.yaml, deck specs, CSV."""

import csv
from pathlib import Path

import yaml
from pptx.dml.color import RGBColor

SKILL_DIR = Path(__file__).resolve().parent.parent
BRAND_PATH = SKILL_DIR / "brand.yaml"
TEMPLATE_PATH = SKILL_DIR / "template.pptx"

# Index of each named layout in template.pptx. Re-map these after swapping in a
# real corporate template: run `python3 scripts/inspect_template.py` and edit here.
LAYOUTS = {
    "title": 0,
    "bullets": 1,
    "section": 2,
    "two_column": 3,
    "title_only": 5,
    "blank": 6,
}

SLIDE_TYPES = ("title", "section", "bullets", "two_column", "table", "chart", "closing")


class DeckError(Exception):
    """A problem with brand.yaml, the deck spec, or the data it points at."""


def load_brand(path: Path = BRAND_PATH) -> dict:
    brand = _load_yaml(path)
    for key in ("colors", "fonts", "rules", "footer", "company"):
        if key not in brand:
            raise DeckError(f"{path.name} is missing '{key}'")
    return brand


def load_spec(path: Path) -> dict:
    spec = _load_yaml(path)
    if not spec.get("slides"):
        raise DeckError(f"{path} has no 'slides'")
    for i, slide in enumerate(spec["slides"], start=1):
        kind = slide.get("type")
        if kind not in SLIDE_TYPES:
            raise DeckError(
                f"slide {i}: type {kind!r} is not one of {', '.join(SLIDE_TYPES)}"
            )
    return spec


def _load_yaml(path: Path) -> dict:
    try:
        text = path.read_text()
    except FileNotFoundError as exc:
        raise DeckError(f"{path} does not exist") from exc
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DeckError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise DeckError(f"{path} should contain a YAML mapping")
    return loaded


def read_csv(path: Path, columns: list[str] | None = None):
    """Return (header, rows) from a CSV, optionally narrowed to `columns`."""
    try:
        with path.open(newline="") as handle:
            rows = list(csv.reader(handle))
    except FileNotFoundError as exc:
        raise DeckError(f"data file {path} does not exist") from exc
    if not rows:
        raise DeckError(f"data file {path} is empty")

    header, body = rows[0], rows[1:]
    if columns is None:
        return header, body

    missing = [c for c in columns if c not in header]
    if missing:
        raise DeckError(
            f"{path.name} has no column(s) {', '.join(missing)}; it has {', '.join(header)}"
        )
    keep = [header.index(c) for c in columns]
    return columns, [[row[i] for i in keep] for row in body]


def to_number(value: str, *, where: str) -> float:
    cleaned = value.strip().replace(",", "").replace("$", "").rstrip("%")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise DeckError(f"{where}: {value!r} is not a number") from exc


def rgb(brand: dict, key: str) -> RGBColor:
    try:
        value = brand["colors"][key]
    except KeyError as exc:
        raise DeckError(f"brand.yaml has no color '{key}'") from exc
    # An all-digit hex colour such as 111827 arrives from YAML as an int; the
    # digits it was written with are what the author meant, not their value.
    text = f"{value:06d}" if isinstance(value, int) else str(value).upper()
    try:
        return RGBColor.from_string(text)
    except ValueError as exc:
        raise DeckError(f"brand.yaml color '{key}' is not RRGGBB hex: {value!r}") from exc


def resolve(spec_path: Path, reference: str) -> Path:
    """Data files in a spec are relative to the spec itself."""
    return (spec_path.parent / reference).resolve()
