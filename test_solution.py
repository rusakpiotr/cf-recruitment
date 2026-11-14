import pandas
import pytest
from pandas.testing import assert_frame_equal

from solution import add_virtual_column

# --- fixtures ----------------------------------------------------------------


@pytest.fixture
def df() -> pandas.DataFrame:
    return pandas.DataFrame({"quantity": [10, 3], "price": [10, 1], "name": ["banana", "apple"]})


# --- valid roles -------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("quantity + price", [20, 4]),
        ("quantity - price", [0, 2]),
        ("quantity * price", [100, 3]),
        ("price - quantity", [0, -2]),
    ],
)
def test_supported_operations(df, role, expected):
    result = add_virtual_column(df, role, "result")

    assert result["result"].tolist() == expected


def test_keeps_original_columns_and_appends_new_one_at_the_end(df):
    result = add_virtual_column(df, "quantity * price", "total")

    assert result.columns.tolist() == ["quantity", "price", "name", "total"]
    assert_frame_equal(result.drop(columns="total"), df)


def test_does_not_modify_input(df):
    original = df.copy()

    add_virtual_column(df, "quantity * price", "total")

    assert_frame_equal(df, original)


def test_same_column_on_both_sides(df):
    result = add_virtual_column(df, "quantity * quantity", "squared")

    assert result["squared"].tolist() == [100, 9]


def test_overwrites_existing_column(df):
    result = add_virtual_column(df, "quantity + price", "price")

    assert result.columns.tolist() == ["quantity", "price", "name"]
    assert result["price"].tolist() == [20, 4]


def test_works_with_floats():
    df = pandas.DataFrame({"a": [1.5, 0.25], "b": [2.0, 4.0]})

    result = add_virtual_column(df, "a * b", "c")

    assert result["c"].tolist() == [3.0, 1.0]


def test_works_on_empty_dataframe_with_columns():
    df = pandas.DataFrame({"a": pandas.Series([], dtype=int), "b": pandas.Series([], dtype=int)})

    result = add_virtual_column(df, "a + b", "c")

    assert result.columns.tolist() == ["a", "b", "c"]
    assert result.empty


# --- invalid input -----------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [
        "",
        "   ",
        "quantity",
        "quantity / price",
        "quantity + ",
        " + price",
        "-quantity",
        "quantity + price + quantity",
        "quantity + + price",
        "quantity price",
        "quantity + missing",
        "missing * price",
        "Quantity + price",
        "quantity + 2",
        "quantity1 + price",
    ],
)
def test_invalid_role_returns_empty_dataframe(df, role):
    result = add_virtual_column(df, role, "result")

    assert result.empty
    assert result.columns.empty


@pytest.mark.parametrize("new_column", ["", "new column", "new-column", "total1"])
def test_invalid_new_column_name_returns_empty_dataframe(df, new_column):
    result = add_virtual_column(df, "quantity + price", new_column)

    assert result.empty


def test_invalid_label_in_dataframe_is_rejected_when_used():
    df = pandas.DataFrame({"col1": [1], "col_two": [2]})

    assert add_virtual_column(df, "col1 + col_two", "total").empty


def test_invalid_label_in_dataframe_is_ignored_when_not_used():
    df = pandas.DataFrame({"col1": [1], "a": [2], "b": [3]})

    result = add_virtual_column(df, "a + b", "total")

    assert result["total"].tolist() == [5]
