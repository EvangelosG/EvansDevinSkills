import pytest
from deckkit import DeckError, load_brand, load_spec, read_csv, resolve, rgb, to_number


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_load_spec_accepts_the_worked_example(tmp_path):
    from deckkit import SKILL_DIR

    spec = load_spec(SKILL_DIR / "example" / "deck.yaml")
    assert [s["type"] for s in spec["slides"]][:3] == ["title", "bullets", "table"]


def test_load_spec_rejects_an_unknown_slide_type(tmp_path):
    path = write(tmp_path, "deck.yaml", "slides:\n  - type: pie chart\n")
    with pytest.raises(DeckError, match="slide 1: type 'pie chart' is not one of"):
        load_spec(path)


def test_load_spec_rejects_a_spec_with_no_slides(tmp_path):
    path = write(tmp_path, "deck.yaml", "title: nothing here\n")
    with pytest.raises(DeckError, match="no 'slides'"):
        load_spec(path)


def test_load_spec_reports_the_missing_file_by_name(tmp_path):
    with pytest.raises(DeckError, match="does not exist"):
        load_spec(tmp_path / "absent.yaml")


def test_load_spec_reports_invalid_yaml(tmp_path):
    path = write(tmp_path, "deck.yaml", "slides: [unclosed\n")
    with pytest.raises(DeckError, match="not valid YAML"):
        load_spec(path)


def test_load_brand_requires_every_section(tmp_path):
    path = write(tmp_path, "brand.yaml", "company: Acme\nfonts: {}\n")
    with pytest.raises(DeckError, match="missing 'colors'"):
        load_brand(path)


def test_read_csv_narrows_to_the_requested_columns(tmp_path):
    path = write(tmp_path, "m.csv", "month,a,b\n2026-01,1,2\n2026-02,3,4\n")
    header, rows = read_csv(path, ["month", "b"])
    assert header == ["month", "b"]
    assert rows == [["2026-01", "2"], ["2026-02", "4"]]


def test_read_csv_names_the_columns_it_could_not_find(tmp_path):
    path = write(tmp_path, "m.csv", "month,a\n2026-01,1\n")
    with pytest.raises(DeckError, match="has no column\\(s\\) revenue; it has month, a"):
        read_csv(path, ["month", "revenue"])


def test_read_csv_rejects_an_empty_file(tmp_path):
    with pytest.raises(DeckError, match="is empty"):
        read_csv(write(tmp_path, "m.csv", ""))


@pytest.mark.parametrize(
    "raw,expected", [("42", 42.0), (" 1,234 ", 1234.0), ("$37.08", 37.08), ("95.9%", 95.9)]
)
def test_to_number_strips_the_usual_formatting(raw, expected):
    assert to_number(raw, where="cell") == expected


def test_to_number_says_where_the_bad_value_was():
    with pytest.raises(DeckError, match="row 3: 'n/a' is not a number"):
        to_number("n/a", where="row 3")


def test_rgb_reads_a_brand_colour(brand):
    assert str(rgb(brand, "accent1")) == brand["colors"]["accent1"].upper()


def test_rgb_accepts_a_hex_colour_yaml_parsed_as_an_int():
    assert str(rgb({"colors": {"dark": 111827}}, "dark")) == "111827"


def test_rgb_rejects_something_that_is_not_a_colour():
    with pytest.raises(DeckError, match="not RRGGBB hex"):
        rgb({"colors": {"dark": "navy"}}, "dark")


def test_rgb_names_a_colour_that_is_not_in_the_brand(brand):
    with pytest.raises(DeckError, match="no color 'chartreuse'"):
        rgb(brand, "chartreuse")


def test_resolve_is_relative_to_the_spec(tmp_path):
    assert resolve(tmp_path / "deck.yaml", "data/m.csv") == tmp_path / "data" / "m.csv"
