"""Markdown renderer for lab report analysis results.

Converts the structured JSON analysis dict into formatted markdown
with emoji severity indicators and GFM tables.
"""
import logging

logger = logging.getLogger(__name__)

# Severity emoji mapping
SEVERITY_EMOJI = {
    "normal": "\U0001f7e2",     # 🟢 Green circle
    "borderline": "\U0001f7e1", # 🟡 Yellow circle
    "critical": "\U0001f534",   # 🔴 Red circle
}

DEFAULT_DISCLAIMER = (
    "This report provides educational insights and clinical associations only. "
    "It is not a diagnosis or treatment recommendation. "
    "Please consult a qualified physician."
)


def render_analysis_markdown(analysis: dict) -> str:
    """Convert analysis JSON to formatted markdown.

    Args:
        analysis: Parsed analysis dict from LLM.

    Returns:
        Formatted markdown string.
    """
    sections = []

    sections.append("# Lab Report Analysis\n")
    sections.append(_render_patient_info(analysis.get("patient_info", {})))
    sections.append(_render_summary(analysis.get("summary", "")))
    sections.append(_render_categories(analysis.get("categories", [])))

    abnormal = analysis.get("abnormal_analysis", "")
    if abnormal:
        sections.append(f"## Abnormal Value Analysis\n\n{abnormal}\n")

    clinical = analysis.get("clinical_associations", "")
    if clinical:
        sections.append(f"## Clinical Associations\n\n{clinical}\n")

    tips = analysis.get("lifestyle_tips", "")
    if tips:
        sections.append(f"## Lifestyle Recommendations\n\n{tips}\n")

    disclaimer = analysis.get("disclaimer", DEFAULT_DISCLAIMER)
    sections.append(f"---\n\n> **Disclaimer:** {disclaimer}\n")

    return "\n".join(sections)


def _render_patient_info(info: dict) -> str:
    """Render the Patient Information section."""
    age = info.get("age", "N/A") or "N/A"
    gender = info.get("gender", "N/A") or "N/A"
    report_date = info.get("report_date", "N/A") or "N/A"

    return (
        "## Patient Information\n\n"
        f"- **Age:** {age}\n"
        f"- **Gender:** {gender}\n"
        f"- **Report Date:** {report_date}\n"
    )


def _render_summary(summary: str) -> str:
    """Render the Summary section."""
    if not summary:
        summary = "No summary available."
    return f"## Summary\n\n{summary}\n"


def _render_categories(categories: list) -> str:
    """Render all category tables with severity emoji indicators."""
    if not categories:
        return "## Test Results\n\nNo test results found.\n"

    parts = ["## Test Results\n"]

    for category in categories:
        name = category.get("name", "Uncategorized")
        tests = category.get("tests", [])

        parts.append(f"### {name}\n")

        if not tests:
            parts.append("No tests in this category.\n")
            continue

        # GFM table header
        parts.append(
            "| Status | Test | Value | Unit | Reference Range | Interpretation |"
        )
        parts.append(
            "|:------:|------|-------|------|-----------------|----------------|"
        )

        for test in tests:
            severity = test.get("severity", "normal")
            emoji = SEVERITY_EMOJI.get(severity, SEVERITY_EMOJI["normal"])
            test_name = _escape_pipe(str(test.get("test_name", "Unknown")))
            value = _escape_pipe(str(test.get("value", "N/A")))
            unit = _escape_pipe(str(test.get("unit", "")))
            ref_range = _escape_pipe(str(test.get("reference_range", "N/A")))
            interpretation = _escape_pipe(str(test.get("interpretation", "")))

            # Add reference source note
            ref_source = test.get("reference_source", "")
            if ref_source == "standard_knowledge":
                ref_range += " *"

            parts.append(
                f"| {emoji} | {test_name} | {value} | {unit} | {ref_range} | {interpretation} |"
            )

        # Add footnote if any test used standard knowledge
        has_standard = any(
            t.get("reference_source") == "standard_knowledge" for t in tests
        )
        if has_standard:
            parts.append(
                "\n*\\* Reference values not available in the report; "
                "ranges based on standard medical knowledge.*"
            )

        parts.append("")  # blank line after table

    return "\n".join(parts)


def _escape_pipe(text: str) -> str:
    """Escape pipe characters to prevent GFM table breakage."""
    return text.replace("|", "\\|")
