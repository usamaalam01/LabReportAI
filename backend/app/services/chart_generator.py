"""Matplotlib-based chart generation for lab report analysis.

Generates bar charts (value vs reference range per category)
and gauge charts (speedometer for borderline/critical values).
"""
import logging
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for Docker

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

# Color palette
COLORS = {
    "normal": "#22c55e",
    "borderline": "#eab308",
    "critical": "#ef4444",
}

BAR_COLORS = {
    "normal": "#22c55e",
    "borderline": "#f59e0b",
    "critical": "#ef4444",
}


def parse_reference_range(ref_str: str) -> tuple[float, float] | None:
    """Parse reference range string into (low, high) tuple.

    Handles formats:
        "13.0 - 17.0", "13.0-17.0"  → (13.0, 17.0)
        "< 200", "<200"             → (0, 200)
        "> 40", ">40"              → (40, 200)  (upper bound estimated)
    """
    if not ref_str or ref_str == "N/A":
        return None

    ref_str = ref_str.strip().rstrip(" *")

    # Range format: "low - high"
    match = re.match(r"([\d.]+)\s*[-–]\s*([\d.]+)", ref_str)
    if match:
        try:
            return (float(match.group(1)), float(match.group(2)))
        except ValueError:
            return None

    # Less than format: "< value"
    match = re.match(r"<\s*([\d.]+)", ref_str)
    if match:
        try:
            return (0, float(match.group(1)))
        except ValueError:
            return None

    # Greater than format: "> value"
    match = re.match(r">\s*([\d.]+)", ref_str)
    if match:
        try:
            low = float(match.group(1))
            return (low, low * 3)
        except ValueError:
            return None

    return None


def _try_numeric(value) -> float | None:
    """Try to convert a value to float. Returns None if not numeric."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def generate_bar_chart(category: dict, output_path: str) -> str | None:
    """Generate a horizontal bar chart for a test category.

    Shows each test's value against its reference range.
    Color-coded by severity.

    Returns the file path if generated, None if no numeric tests.
    """
    tests = category.get("tests", [])

    # Filter to numeric tests with parseable reference ranges
    chart_data = []
    for test in tests:
        value = _try_numeric(test.get("value"))
        if value is None:
            continue
        ref = parse_reference_range(str(test.get("reference_range", "")))
        if ref is None:
            continue
        chart_data.append({
            "name": test.get("test_name", "Unknown"),
            "value": value,
            "ref_low": ref[0],
            "ref_high": ref[1],
            "severity": test.get("severity", "normal"),
        })

    if not chart_data:
        return None

    n = len(chart_data)
    fig_height = max(2.5, n * 0.7 + 1.0)
    fig, ax = plt.subplots(figsize=(8, fig_height))

    y_positions = np.arange(n)
    bar_height = 0.4

    for i, item in enumerate(chart_data):
        color = BAR_COLORS.get(item["severity"], BAR_COLORS["normal"])

        # Draw reference range as light gray band
        ax.barh(
            i, item["ref_high"] - item["ref_low"], left=item["ref_low"],
            height=0.6, color="#e5e7eb", edgecolor="#d1d5db", linewidth=0.5,
            zorder=1,
        )

        # Draw patient value as colored bar
        ax.barh(
            i, item["value"], height=bar_height,
            color=color, edgecolor="white", linewidth=0.5,
            zorder=2,
        )

        # Value label
        ax.text(
            item["value"] + (ax.get_xlim()[1] or item["value"]) * 0.02, i,
            f'{item["value"]:.1f}',
            va="center", ha="left", fontsize=8, fontweight="bold",
            zorder=3,
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels([d["name"] for d in chart_data], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Value", fontsize=9)
    ax.set_title(category.get("name", "Test Results"), fontsize=11, fontweight="bold", pad=10)

    # Adjust x-axis to accommodate labels
    x_max = max(
        max(d["value"], d["ref_high"]) for d in chart_data
    ) * 1.2
    ax.set_xlim(0, x_max)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#e5e7eb", edgecolor="#d1d5db", label="Reference Range"),
        Patch(facecolor="#22c55e", label="Normal"),
        Patch(facecolor="#f59e0b", label="Borderline"),
        Patch(facecolor="#ef4444", label="Critical"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=7, framealpha=0.9)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info(f"Bar chart saved: {output_path}")
    return output_path


def generate_gauge_chart(test: dict, output_path: str) -> str | None:
    """Generate a speedometer-style gauge chart for one test.

    Only for borderline or critical severity with numeric values.
    Shows green/yellow/red zones with a needle pointer.

    Returns the file path if generated, None otherwise.
    """
    value = _try_numeric(test.get("value"))
    if value is None:
        return None

    severity = test.get("severity", "normal")
    if severity == "normal":
        return None

    ref = parse_reference_range(str(test.get("reference_range", "")))
    if ref is None:
        return None

    ref_low, ref_high = ref
    ref_range = ref_high - ref_low

    # Define gauge range: extend beyond reference range
    gauge_min = max(0, ref_low - ref_range * 0.5)
    gauge_max = ref_high + ref_range * 0.8
    if value > gauge_max:
        gauge_max = value * 1.2
    if value < gauge_min:
        gauge_min = value * 0.8 if value > 0 else 0

    gauge_span = gauge_max - gauge_min
    if gauge_span == 0:
        return None

    fig, ax = plt.subplots(figsize=(3.5, 2.2), subplot_kw={"aspect": "equal"})

    # Draw gauge arc (180 degrees, bottom half)
    # Zones: critical-low (red) | borderline-low (yellow) | normal (green) | borderline-high (yellow) | critical-high (red)
    borderline_margin = ref_range * 0.15

    zones = []
    # Critical low zone
    if ref_low - borderline_margin > gauge_min:
        zones.append((gauge_min, ref_low - borderline_margin, COLORS["critical"]))
    # Borderline low zone
    zones.append((max(gauge_min, ref_low - borderline_margin), ref_low, COLORS["borderline"]))
    # Normal zone
    zones.append((ref_low, ref_high, COLORS["normal"]))
    # Borderline high zone
    zones.append((ref_high, min(gauge_max, ref_high + borderline_margin), COLORS["borderline"]))
    # Critical high zone
    if ref_high + borderline_margin < gauge_max:
        zones.append((ref_high + borderline_margin, gauge_max, COLORS["critical"]))

    for zone_min, zone_max, color in zones:
        start_angle = 180 - ((zone_min - gauge_min) / gauge_span) * 180
        end_angle = 180 - ((zone_max - gauge_min) / gauge_span) * 180
        theta1 = min(start_angle, end_angle)
        theta2 = max(start_angle, end_angle)

        wedge = patches.Wedge(
            (0, 0), 1.0, theta1, theta2,
            width=0.3, facecolor=color, edgecolor="white", linewidth=0.5,
        )
        ax.add_patch(wedge)

    # Draw needle
    needle_angle_deg = 180 - ((value - gauge_min) / gauge_span) * 180
    needle_angle_rad = math.radians(needle_angle_deg)
    needle_length = 0.75

    ax.plot(
        [0, needle_length * math.cos(needle_angle_rad)],
        [0, needle_length * math.sin(needle_angle_rad)],
        color="#1f2937", linewidth=2.5, zorder=5,
    )
    # Needle center dot
    circle = plt.Circle((0, 0), 0.06, color="#1f2937", zorder=6)
    ax.add_patch(circle)

    # Labels
    ax.text(0, -0.25, f"{value}", ha="center", va="center",
            fontsize=14, fontweight="bold", color="#1f2937")
    ax.text(0, -0.42, test.get("unit", ""), ha="center", va="center",
            fontsize=8, color="#6b7280")
    ax.text(0, 1.15, test.get("test_name", ""), ha="center", va="center",
            fontsize=10, fontweight="bold", color="#1f2937")

    # Min/max labels
    ax.text(-1.05, -0.05, f"{gauge_min:.0f}", ha="center", va="center",
            fontsize=7, color="#9ca3af")
    ax.text(1.05, -0.05, f"{gauge_max:.0f}", ha="center", va="center",
            fontsize=7, color="#9ca3af")

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.55, 1.3)
    ax.axis("off")

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white",
                transparent=False)
    plt.close(fig)

    logger.info(f"Gauge chart saved: {output_path}")
    return output_path


def generate_charts_for_report(analysis: dict, job_id: str) -> dict:
    """Generate all charts for a report analysis.

    Returns dict mapping: { category_index: { "bar": path, "gauges": [paths] } }
    """
    settings = get_settings()
    charts_dir = Path(settings.outputs_path) / job_id / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    categories = analysis.get("categories", [])
    result = {}

    for idx, category in enumerate(categories):
        category_charts = {"bar": None, "gauges": []}

        # Generate bar chart for the category
        bar_path = str(charts_dir / f"bar_{idx}.png")
        try:
            bar_result = generate_bar_chart(category, bar_path)
            category_charts["bar"] = bar_result
        except Exception as e:
            logger.warning(f"Bar chart failed for category {idx}: {e}")

        # Generate gauge charts for borderline/critical tests
        for test_idx, test in enumerate(category.get("tests", [])):
            severity = test.get("severity", "normal")
            if severity in ("borderline", "critical"):
                gauge_path = str(charts_dir / f"gauge_{idx}_{test_idx}.png")
                try:
                    gauge_result = generate_gauge_chart(test, gauge_path)
                    if gauge_result:
                        category_charts["gauges"].append(gauge_result)
                except Exception as e:
                    logger.warning(f"Gauge chart failed for test {test_idx}: {e}")

        result[idx] = category_charts

    logger.info(f"Charts generated for {len(result)} categories")
    return result
