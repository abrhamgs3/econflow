"""EconFlow visualization subpackage — publication-quality figures."""

from econflow.visualization.figures import (
    ai_coefficient_comparison,
    ai_tfp_scatter,
    ai_tfp_trend,
    missingness_profile,
)

__all__ = [
    "ai_tfp_scatter",
    "ai_tfp_trend",
    "ai_coefficient_comparison",
    "missingness_profile",
]

from econflow.visualization.style import COLORS, WIDTH_FULL, apply_style

__all__ += ["apply_style", "COLORS", "WIDTH_FULL"]
