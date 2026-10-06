"""Download the CDPH weekly WNV human case file to data/raw/.

Run from the project root:  python -m src.download_wnv
"""

from src.config import RAW, WNV_COLUMNS, WNV_URL
from src.fetch import get, log_download

OUT = RAW / "wnv_human_cases.csv"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    r = get(WNV_URL, timeout=120)  # the portal redirects to a signed S3 link
    header = r.text.lstrip("﻿").split("\n", 1)[0].strip()
    if [c.strip() for c in header.split(",")] != WNV_COLUMNS:
        raise SystemExit(
            f"Unexpected WNV file. Expected columns {WNV_COLUMNS}, got: {header[:200]!r}"
        )
    OUT.write_bytes(r.content)
    log_download("wnv", WNV_URL)
    n_rows = r.text.strip().count("\n")
    print(f"Wrote {OUT.relative_to(RAW.parents[1])} ({n_rows:,} rows)")


if __name__ == "__main__":
    main()
