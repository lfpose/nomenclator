import pandas as pd
from io import StringIO


class CSVError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


def parse_csv(raw: bytes) -> list[str]:
    try:
        text = raw.decode("utf-8-sig")  # strips BOM
    except UnicodeDecodeError:
        raise CSVError("encoding_invalid", "File is not UTF-8.")
    
    if not text.strip():
        raise CSVError("input_empty", "No data found in CSV file.")

    sample = text[:2048]
    comma = sample.count(",")
    semi = sample.count(";")
    
    # Check for unsupported delimiters
    # If we have neither comma nor semicolon, but have other common delimiters, raise error
    if comma == 0 and semi == 0:
        # Check for common unsupported delimiters in the first line
        first_line = text.split("\n")[0] if "\n" in text else text
        unsupported = any(c in first_line for c in "|\t")
        if unsupported:
            raise CSVError("delimiter_unknown", "CSV delimiter must be comma or semicolon.")
        # No delimiters found - single-column CSV, default to comma
        delim = ","
    else:
        delim = "," if comma >= semi else ";"

    try:
        df = pd.read_csv(
            StringIO(text),
            sep=delim,
            dtype=str,
            keep_default_na=False,
            na_values=[],
            skip_blank_lines=True,
            header=None,
        )
    except Exception as e:
        raise CSVError("parse_failed", f"Failed to parse CSV: {e}")

    if df.shape[0] == 0:
        raise CSVError("input_empty", "No data rows.")
    if df.shape[0] > 50_000:
        raise CSVError("input_too_large", f"Row count {df.shape[0]} exceeds 50,000.")

    return df.iloc[:, 0].tolist()


def parse_text(raw: str) -> list[str]:
    lines = [line.strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise CSVError("input_empty", "No titles found.")
    if len(lines) > 50_000:
        raise CSVError("input_too_large", f"Line count {len(lines)} exceeds 50,000.")
    return lines
