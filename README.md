# Setup

Requires Python 3.12 or newer (tested on 3.12, 3.13 and 3.14).

## With pdm

```bash
pdm install          # installs pandas and the dev dependencies (pytest)
pdm run pipeline     # runs pipeline.py and writes revenue_by_region.csv
pdm run test         # runs all tests
```

## Without pdm

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python pipeline.py   # writes revenue_by_region.csv
pytest               # runs all tests
```

`requirements.txt` and `requirements-dev.txt` are exported from `pdm.lock`, so both setups use
the same package versions.

# Assumptions

## Part 1: `add_virtual_column`

- **The new column is named after `new_column`.** The example in the task passes `"total"` but
  shows a column called `price_total`; the function uses the name it is given (`total`).
- **A role is exactly two column labels joined by one operator** (`+`, `-` or `*`), with optional
  spaces around them. Anything else, such as `a + b + c`, `a / b` or `a + 2`, gives an empty
  DataFrame.
- **"Letters" means ASCII letters** (`A`–`Z`, `a`–`z`). Labels with digits, spaces, hyphens or
  non-ASCII letters are rejected.
- **Only the labels used in the role and `new_column` are validated.** Other columns of `df` may
  have any names; an invalid label that the role does not use does not make the result empty.
- **An existing column with the name `new_column` is overwritten**, and the input DataFrame is
  never modified (the function returns a copy).

## Part 2: pipeline

- **Every value is read as text first.** `sales.csv` is read with `dtype=str, keep_default_na=False`,
  so pandas does not guess column types and empty fields stay as `""`. Each numeric column is
  converted explicitly after cleaning, so one malformed value cannot silently change the type of
  a whole column.
- **Column names and text values are normalized** to lowercase, with surrounding whitespace removed
  and inner spaces replaced by `_` (`"Order ID"` → `order_id`, `" South"` → `south`,
  `"Office chair"` → `office_chair`). Regions in `revenue_by_region.csv` are therefore lowercase.
- **The `TOTAL` row is not data.** It is a summary line of the export and is removed from the
  data. Its numbers are used only as a checksum: the tests check that the cleaned quantities and
  discounts add up to them (37150 and 65924.67) before duplicates are removed, so no other
  cleaning step loses or changes a value. The export's total counts the duplicate lines too.
- **A comma in a unit price is a decimal separator** (`"59,00"` = 59.00). All such prices have
  exactly two digits after the comma, so they cannot be thousands separators.
- **A missing unit price is the product's price.** In the file every product has exactly one unit
  price, so an empty price is filled with the price of the same product. If a price could not be
  determined this way, the pipeline stops with an error instead of guessing.
- **A space in a quantity is a thousands separator** (`"1 762"` = 1762). These rows are kept, not
  dropped, because the value can be read unambiguously.
- **An empty discount means no discount** and is treated as `0`. As stated in the task, the discount
  is an amount of money taken off the whole line, not a percentage and not per unit.
- **Revenue = quantity × unit price − discount**, computed with `add_virtual_column` in two steps
  (`quantity * unit_price`, then `revenue - discount`).
- **Per-order revenue is not written to a file.** The task asks to add a `revenue` column, but the
  only output file it names is `revenue_by_region.csv`. The column is therefore kept in memory:
  `run()` returns the cleaned DataFrame with `revenue` for every order (this is what the tests
  check), and only the per-region totals are written to disk.
- **`revenue_by_region.csv` also has quantity and discount totals.** The task asks only for the
  total revenue of each region; the file has one row per region with the sums of `quantity`,
  `discount` and `revenue`, which makes the revenue easy to check against the source data.
- **A negative quantity is a return.** It is kept, so its revenue is negative and lowers the
  revenue of its region. Dropping it or taking the absolute value would overstate revenue.
- **Duplicate rows are removed.** Each duplicate repeats the previous line in every column,
  including the order ID. A second purchase would get its own order ID, so these are lines
  exported twice, not real orders. Duplicates are compared after cleaning, so a price written as
  `"59,00"` and `"59.00"` counts as the same value. The first line of each pair is kept.

# Problems found in sales.csv

The file has 1507 rows below the header; 1505 of them are order lines, and 1500 remain after
removing duplicates.

| Problem | Rows | How it is handled |
|---|---:|---|
| Summary row `TOTAL` at the end of the file | 1 | Removed |
| Header line repeated inside the file (line 753) | 1 | Removed |
| Column name with trailing space (`"Quantity "`) | – | Column names stripped and normalized |
| Region with surrounding whitespace (`" South"`, `"west  "`, …) | 8 | Stripped |
| Region in a different case (`"EAST"`, `"north"`, …) | 10 (3 of them also have whitespace) | Lowercased |
| Unit price with decimal comma (`"59,00"`) | 7 | Comma replaced with a dot |
| Empty unit price | 4 | Filled with the unit price of the same product |
| Quantity with a space as thousands separator (`"1 762"`) | 4 | Space removed |
| Empty discount | 963 | Set to `0` |
| Exact duplicate rows (same order ID and same values) | 5 | Removed, first line kept (see assumptions) |
| Negative quantity (`-2` … `-5`) | 6 | Kept as returns, giving negative revenue (see assumptions) |