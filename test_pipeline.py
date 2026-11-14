from pathlib import Path

import pandas
import pytest
from pandas.testing import assert_frame_equal

import pipeline

ROOT = Path(__file__).parent
SALES_CSV = ROOT / "sales.csv"
COMMITTED_OUTPUT = ROOT / "revenue_by_region.csv"


# --- helpers and fixtures ----------------------------------------------------


def read_raw(path: Path = SALES_CSV) -> pandas.DataFrame:
    return pandas.read_csv(path, dtype=str, keep_default_na=False)


@pytest.fixture
def output_path(tmp_path, monkeypatch) -> Path:
    """Redirect the pipeline output for the tests that check saving."""
    path = tmp_path / "revenue_by_region.csv"
    monkeypatch.setattr(pipeline, "OUTPUT_FILE_PATH", str(path))
    return path


@pytest.fixture
def cleaned() -> pandas.DataFrame:
    return pipeline.run(read_raw(), save=False)


# --- single cleaning steps ---------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [("59.00", 59.0), ("59,00", 59.0), ("1249.99", 1249.99), ("21,5", 21.5)],
)
def test_parse_price(value, expected):
    assert pipeline._parse_price(value) == expected


def test_parse_price_empty_is_nan():
    assert pandas.isna(pipeline._parse_price(""))


def test_normalize_column_names():
    df = pandas.DataFrame(columns=["Order ID", "Quantity ", " Unit Price"])

    pipeline._normalize_columns(df)

    assert df.columns.tolist() == ["order_id", "quantity", "unit_price"]


def test_normalize_values():
    df = pandas.DataFrame({"region": [" South", "west  ", "EAST", "north"]})

    pipeline.normalize_csv(df)

    assert df["region"].tolist() == ["south", "west", "east", "north"]


def test_clean_prices_fills_missing_price_from_same_product():
    df = pandas.DataFrame(
        {
            "order_id": ["a", "b", "c", "d"],
            "product": ["mouse", "mouse", "headset", "mouse"],
            "unit_price": ["29.50", "", "119,00", "29,50"],
        }
    )

    pipeline.clean_prices(df)

    assert df["unit_price"].tolist() == [29.5, 29.5, 119.0, 29.5]


def test_clean_prices_raises_when_price_cannot_be_determined():
    df = pandas.DataFrame(
        {"order_id": ["a", "b"], "product": ["mouse", "headset"], "unit_price": ["29.50", ""]}
    )

    with pytest.raises(ValueError, match="Cannot determine unit price"):
        pipeline.clean_prices(df)


@pytest.mark.parametrize(
    ("value", "expected"), [("12", 12), ("1 762", 1762), ("1_762", 1762), ("-3", -3)]
)
def test_clean_quantities(value, expected):
    df = pandas.DataFrame({"quantity": [value]})

    pipeline.clean_quantities(df)

    assert df["quantity"].tolist() == [expected]


def test_empty_discount_becomes_zero():
    df = pandas.DataFrame({"discount": ["", "12.50"]})

    pipeline.fill_empty_discounts(df)

    assert df["discount"].tolist() == [0.0, 12.5]


def test_remove_duplicates_keeps_first_of_identical_rows():
    df = pandas.DataFrame({"order_id": ["a", "a", "b", "c"], "quantity": [1, 1, 1, 2]})

    result = pipeline.remove_duplicates(df)

    assert result["order_id"].tolist() == ["a", "b", "c"]


def test_revenue_is_quantity_times_price_minus_discount():
    df = pandas.DataFrame(
        {"quantity": [32, 1], "unit_price": [249.0, 59.0], "discount": [398.4, 0.0]}
    )

    result = pipeline.add_virtual_revenue_column(df)

    assert result["revenue"].tolist() == pytest.approx([7569.6, 59.0])


# --- whole pipeline on sales.csv ---------------------------------------------


def test_run_does_not_modify_input():
    raw = read_raw()
    original = raw.copy()

    pipeline.run(raw, save=False)

    assert_frame_equal(raw, original)


def test_run_saves_revenue_by_region_by_default(output_path):
    cleaned = pipeline.run(read_raw())

    assert_frame_equal(pandas.read_csv(output_path), pipeline.revenue_by_region(cleaned))


def test_run_without_save_writes_nothing(output_path):
    pipeline.run(read_raw(), save=False)

    assert not output_path.exists()


def test_removes_total_and_repeated_header_rows(cleaned):
    assert not cleaned["order_id"].isin(["total", "order_id"]).any()


def test_number_of_order_lines(cleaned):
    """1507 rows below the header - TOTAL row - repeated header - 5 duplicates."""
    assert len(read_raw()) == 1507
    assert len(cleaned) == 1500


def test_regions_are_normalized(cleaned):
    assert sorted(cleaned["region"].unique()) == ["central", "east", "north", "south", "west"]


def test_numeric_columns_are_fully_parsed(cleaned):
    for column in ["quantity", "unit_price", "discount", "revenue"]:
        assert pandas.api.types.is_numeric_dtype(cleaned[column]), column
        assert cleaned[column].notna().all(), column


def test_every_product_has_a_single_price(cleaned):
    assert (cleaned.groupby("product")["unit_price"].nunique() == 1).all()


def test_revenue_formula_on_every_row(cleaned):
    expected = cleaned["quantity"] * cleaned["unit_price"] - cleaned["discount"]

    assert cleaned["revenue"].tolist() == pytest.approx(expected.tolist())


def test_totals_match_total_row_of_the_export(monkeypatch):
    """The TOTAL row of sales.csv sums quantity and discount over all lines, duplicates included.

    Every cleaning step except removing duplicates must keep these sums unchanged.
    """
    monkeypatch.setattr(pipeline, "remove_duplicates", lambda df: df)
    raw = read_raw()
    cleaned = pipeline.run(raw, save=False)
    total_row = raw[raw.iloc[:, 0] == "TOTAL"].iloc[0]
    quantity_column = next(c for c in raw.columns if c.strip().lower() == "quantity")

    assert cleaned["quantity"].sum() == int(total_row[quantity_column])
    assert cleaned["discount"].sum() == pytest.approx(float(total_row["Discount"]))


def test_revenue_by_region(cleaned):
    result = pipeline.revenue_by_region(cleaned)

    regions = result[result["region"] != "TOTAL"]

    assert result.columns.tolist() == ["region", "quantity", "discount", "revenue"]
    assert regions["region"].tolist() == ["central", "east", "north", "south", "west"]

    expected = cleaned.groupby("region")["revenue"].sum()
    assert regions.set_index("region")["revenue"].to_dict() == pytest.approx(expected.to_dict())


def test_revenue_by_region_ends_with_fixed_total_row(cleaned):
    """The TOTAL row is recomputed from the cleaned data: without duplicates, with revenue."""
    result = pipeline.revenue_by_region(cleaned)
    total = result.iloc[-1]

    assert (result["region"] == "TOTAL").sum() == 1
    assert total["region"] == "TOTAL"
    assert total["quantity"] == cleaned["quantity"].sum() == 37054
    assert total["discount"] == pytest.approx(cleaned["discount"].sum()) == 65793.77
    assert total["revenue"] == pytest.approx(cleaned["revenue"].sum()) == 2570247.03


def test_committed_output_is_up_to_date(cleaned):
    """revenue_by_region.csv in the repository must match what pipeline.py writes now."""
    assert_frame_equal(pandas.read_csv(COMMITTED_OUTPUT), pipeline.revenue_by_region(cleaned))


def test_negative_quantities_are_kept_as_returns(cleaned):
    returns = cleaned[cleaned["quantity"] < 0]

    assert len(returns) == 6
    assert (returns["revenue"] < 0).all()


def test_duplicate_rows_are_removed(cleaned):
    assert not cleaned.duplicated().any()
    assert cleaned["order_id"].is_unique
