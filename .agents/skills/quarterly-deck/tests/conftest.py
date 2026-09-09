import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from deckkit import load_brand  # noqa: E402


@pytest.fixture(scope="session")
def brand():
    return load_brand()


@pytest.fixture(scope="session")
def example_deck(tmp_path_factory, brand):
    """The worked example, built once. Most tests only read it."""
    from build_deck import DeckBuilder
    from deckkit import TEMPLATE_PATH, load_spec

    spec_path = SKILL_DIR / "example" / "deck.yaml"
    spec = load_spec(spec_path)
    prs = DeckBuilder(brand, TEMPLATE_PATH).build(spec, spec_path)
    out = tmp_path_factory.mktemp("deck") / "example.pptx"
    prs.save(out)
    return out
