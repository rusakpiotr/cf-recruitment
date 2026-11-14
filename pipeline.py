import pandas

from solution import add_virtual_column

INPUT_FILE_PATH = "sales.csv"
OUTPUT_FILE_PATH = "revenue_by_region.csv"


# --- helpers -----------------------------------------------------------------


def _normalize_column(s: str | pandas.DataFrame) -> str:
    return s.str.lower().str.strip().str.replace(" ", "_")


def _parse_price(value: str) -> float:
    """Parse a unit price such as ``"59.00"`` or ``"59,00"`` (decimal comma).

    An empty string becomes NaN, so it can be filled in later.
    """
    if value == "":
        return float("nan")
    return float(value.replace(",", "."))


def _normalize_columns(df: pandas.DataFrame) -> None:
    df.columns = _normalize_column(df.columns)


# --- cleaning steps ----------------------------------------------------------


def normalize_csv(df: pandas.DataFrame) -> None:
    for label in df.columns:
        df[label] = _normalize_column(df[label])


def clean_prices(df: pandas.DataFrame) -> None:
    """Convert ``unit_price`` to float and fill in missing prices.

    Every product has a single unit price in the data, so a missing price is
    filled with the most common price of the same product.
    """
    df["unit_price"] = df["unit_price"].map(_parse_price)

    # A product with no price at all has an empty mode; it stays NaN and is reported below.
    price_per_product = df.groupby("product")["unit_price"].agg(
        lambda s: next(iter(s.mode()), float("nan"))
    )
    df["unit_price"] = df["unit_price"].fillna(df["product"].map(price_per_product))

    if df["unit_price"].isna().any():
        missing = df.loc[df["unit_price"].isna(), ["order_id", "product"]]
        raise ValueError(f"Cannot determine unit price for rows:\n{missing}")


def clean_quantities(df: pandas.DataFrame) -> None:
    """Convert ``quantity`` to int.

    Some quantities use a space as a thousands separator ("1 762"); after
    ``normalize_csv`` the space is an underscore ("1_762"), so both are removed.
    """
    df["quantity"] = df["quantity"].str.replace(r"[\s_]", "", regex=True).astype(int)


def fill_empty_discounts(df: pandas.DataFrame) -> None:
    df["discount"] = df["discount"].replace("", "0").astype(float)


def remove_duplicates(df: pandas.DataFrame) -> pandas.DataFrame:
    """Drop rows that repeat an earlier row in every column, including the order ID.

    Run after the other cleaning steps, so that e.g. ``"59,00"`` and ``"59.00"`` compare equal.
    """
    return df.drop_duplicates()


# --- revenue -----------------------------------------------------------------


def add_virtual_revenue_column(df: pandas.DataFrame) -> pandas.DataFrame:
    df = add_virtual_column(df, "quantity * unit_price", "revenue")
    return add_virtual_column(df, "revenue - discount", "revenue")


def revenue_by_region(df: pandas.DataFrame) -> pandas.DataFrame:
    """Sum quantity, discount and revenue of each region, with a ``TOTAL`` row at the end.

    The ``TOTAL`` row replaces the one removed from ``sales.csv``: it is recomputed from the
    cleaned data, so it no longer counts duplicates and it also has the total revenue.
    Money sums are rounded to cents to hide floating-point noise.
    """
    columns = ["quantity", "discount", "revenue"]
    by_region = df.groupby("region", as_index=False)[columns].sum()
    # Sum column by column, so that quantity stays an integer.
    total = pandas.DataFrame([{"region": "TOTAL"} | {c: by_region[c].sum() for c in columns}])
    by_region = pandas.concat([by_region, total], ignore_index=True)
    by_region[["discount", "revenue"]] = by_region[["discount", "revenue"]].round(2)
    return by_region


# --- pipeline ----------------------------------------------------------------


def run(df: pandas.DataFrame, save: bool = True) -> pandas.DataFrame:
    """Run every cleaning step on a copy of ``df`` and return the cleaned copy.

    ``df`` should be read with ``dtype=str, keep_default_na=False``. It is not modified.
    With ``save=True`` the revenue of each region is written to ``OUTPUT_FILE_PATH``;
    the tests pass ``save=False``, so they never overwrite the committed file.
    """
    df = df.copy()
    _normalize_columns(df)
    df = df[df["order_id"] != "TOTAL"]
    normalize_csv(df)
    df = df[df["order_id"] != "order_id"].copy()
    clean_prices(df)
    clean_quantities(df)
    fill_empty_discounts(df)
    df = remove_duplicates(df)
    df = add_virtual_revenue_column(df)
    if save:
        revenue_by_region(df).to_csv(OUTPUT_FILE_PATH, sep=",", index=False)
    return df


# --- entry point -------------------------------------------------------------


if __name__ == "__main__":
    df = run(pandas.read_csv(INPUT_FILE_PATH, dtype=str, keep_default_na=False))
