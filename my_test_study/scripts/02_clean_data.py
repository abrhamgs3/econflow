"""
scripts/02_clean_data.py — Merge and clean raw data into a panel CSV for my_test_study.

Reads from data/raw/ and writes data/processed/panel.csv.
Run after scripts/01_download_data.py:

    python scripts/02_clean_data.py
"""

from pathlib import Path

RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = PROCESSED_DIR / "panel.csv"


def main() -> None:
    # TODO: implement data cleaning and merging
    # The output must be a CSV with at least:
    #   - entity column (matches config.yaml data.entity_col)
    #   - time column   (matches config.yaml data.time_col)
    #   - dependent and regressor columns
    raise NotImplementedError(
        "Edit this script to build data/processed/panel.csv from your raw data."
    )


if __name__ == "__main__":
    main()
    print(f"Written: {OUTPUT_FILE}")
