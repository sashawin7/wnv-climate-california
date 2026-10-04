"""Download the CDPH weekly WNV human case file to data/raw/.

Run from the project root:  python -m src.download_wnv
"""

import requests

from src.config import RAW, WNV_URL

OUT = RAW / "wnv_human_cases.csv"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    r = requests.get(WNV_URL, timeout=120)  # the portal redirects to a signed S3 link
    r.raise_for_status()
    OUT.write_bytes(r.content)
    n_rows = r.text.count("\n") - 1
    print(f"Wrote {OUT.relative_to(RAW.parents[1])} ({n_rows:,} rows)")


if __name__ == "__main__":
    main()
