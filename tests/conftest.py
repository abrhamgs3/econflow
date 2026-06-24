"""
tests/conftest.py — Shared pytest fixtures for the EconFlow test suite.

All fixtures reference ``src/econflow/`` — the authoritative package.
Fixtures that depend on sub-systems not yet implemented return ``None``;
tests that require them should be marked ``@pytest.mark.skip``.

Fixture inventory
-----------------
sample_panel        Generic synthetic balanced panel (10 entities × 10 periods).
world_bank_raw      Well-formed World Bank API v2 JSON response stub.
oecd_raw            OECD SDMX-JSON response skeleton.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Panel fixtures
# ---------------------------------------------------------------------------

N_ENTITIES = 10
N_PERIODS  = 10
ENTITIES   = [f"E{i:02d}" for i in range(N_ENTITIES)]
PERIODS    = list(range(2010, 2010 + N_PERIODS))
RNG        = np.random.default_rng(42)


@pytest.fixture(scope="session")
def sample_panel() -> pd.DataFrame:
    """
    Generic synthetic balanced panel: 10 entities × 10 periods (100 observations).

    Columns
    -------
    entity, time, outcome, treatment, covariate_1, covariate_2,
    trade_openness, investment_share, tertiary_enrol

    These names are intentionally generic so the fixture can be reused across
    tests that exercise core platform utilities (validators, merging, feature
    engineering) without coupling them to the AI & Productivity paper's
    specific variable names.
    """
    rows = [
        {
            "entity":           c,
            "time":             y,
            "outcome":          RNG.normal(0.02, 0.03),
            "treatment":        RNG.uniform(0.0, 1.0),
            "covariate_1":      RNG.normal(9.5, 1.0),
            "covariate_2":      RNG.normal(0.5, 0.2),
            "log_capital":      RNG.normal(12.0, 1.5),
            "trade_openness":   RNG.uniform(0.3, 1.5),
            "investment_share": RNG.uniform(0.15, 0.40),
            "tertiary_enrol":   RNG.uniform(20.0, 90.0),
        }
        for c in ENTITIES
        for y in PERIODS
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Raw API response fixtures (used by ingestion tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def world_bank_raw() -> list:
    """
    Minimal well-formed World Bank API v2 JSON response for two observations.
    """
    return [
        {"page": 1, "pages": 1, "per_page": 50, "total": 2},
        [
            {
                "indicator": {"id": "IT.NET.USER.ZS", "value": "Individuals using the Internet"},
                "country": {"id": "US", "value": "United States"},
                "countryiso3code": "USA",
                "date": "2020",
                "value": 90.1,
                "unit": "",
                "obs_status": "",
                "decimal": 1,
            },
            {
                "indicator": {"id": "IT.NET.USER.ZS", "value": "Individuals using the Internet"},
                "country": {"id": "DE", "value": "Germany"},
                "countryiso3code": "DEU",
                "date": "2020",
                "value": 88.4,
                "unit": "",
                "obs_status": "",
                "decimal": 1,
            },
        ],
    ]


@pytest.fixture(scope="session")
def oecd_raw() -> dict:
    """
    Skeleton OECD SDMX-JSON response structure for unit tests.
    """
    return {
        "header": {
            "id": "test",
            "test": True,
            "prepared": "2024-01-01T00:00:00",
            "sender": {"id": "OECD"},
        },
        "dataSets": [
            {
                "action": "Information",
                "series": {
                    "0:0:0:0": {
                        "attributes": [0],
                        "observations": {
                            "0": [42.3, 0, None],
                            "1": [43.1, 0, None],
                        },
                    }
                },
            }
        ],
        "structure": {
            "dimensions": {
                "series": [
                    {"id": "LOCATION", "values": [{"id": "USA", "name": "United States"}]},
                    {"id": "INDICATOR", "values": [{"id": "GERD", "name": "GERD"}]},
                    {"id": "MEASURE", "values": [{"id": "PC_GDP", "name": "% of GDP"}]},
                    {"id": "POWERCODE", "values": [{"id": "0", "name": "Units"}]},
                ],
                "observation": [
                    {
                        "id": "TIME_PERIOD",
                        "values": [
                            {"id": "2019", "name": "2019"},
                            {"id": "2020", "name": "2020"},
                        ],
                    }
                ],
            }
        },
    }
