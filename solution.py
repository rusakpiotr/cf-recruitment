import operator
import re

import pandas

OPERATORS = {"+": operator.add, "-": operator.sub, "*": operator.mul}


# --- helpers -----------------------------------------------------------------


def _validate_label_name(label_name: str) -> bool:
    return re.fullmatch(r"[A-Za-z_]+", label_name) is not None


# --- public function ---------------------------------------------------------


def add_virtual_column(df: pandas.DataFrame, role: str, new_column: str) -> pandas.DataFrame:
    """Return a copy of ``df`` with a new column computed from two existing columns.

    Args:
        df: Source DataFrame. It is not modified.
        role: Expression in the form ``"<label> <op> <label>"``, where ``<op>``
            is ``+``, ``-`` or ``*``. Spaces around labels and the operator are allowed.
        new_column: Name of the column to add. If it already exists, it is overwritten.

    Returns:
        A copy of ``df`` with ``new_column`` added, or an empty DataFrame if ``role``
        is malformed, a label contains anything other than letters and underscores,
        or a referenced column does not exist in ``df``.
    """
    match = re.search(r"[+\-*]", role)
    if match is None:
        return pandas.DataFrame()

    first_label = role[: match.start()].strip()
    second_label = role[match.start() + 1 :].strip()

    if (
        not _validate_label_name(new_column)
        or not _validate_label_name(first_label)
        or not _validate_label_name(second_label)
        or first_label not in df.columns
        or second_label not in df.columns
    ):
        return pandas.DataFrame()

    df = df.copy()
    df[new_column] = OPERATORS[match.group()](df[first_label], df[second_label])

    return df
