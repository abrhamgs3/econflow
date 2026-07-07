"""
scripts/01_download_data.py — Download raw data for my_test_study.

Edit this script to add your data sources.  When complete, run:

    python scripts/01_download_data.py

All output files should be written to data/raw/.
"""

from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    # TODO: implement data download
    # Example: download from World Bank, OECD, or a local CSV
    raise NotImplementedError(
        "Edit this script to download your raw data files. "
        "Write output files to data/raw/."
    )


if __name__ == "__main__":
    main()
