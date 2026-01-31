"""WeasyPrint-based PDF generation for lab report analysis.

Renders a Jinja2 HTML template with analysis data and chart images,
then converts to PDF via WeasyPrint.
"""
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.config import get_settings

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path("/app/templates/pdf")

SEVERITY_COLORS = {
    "normal": "#22c55e",
    "borderline": "#eab308",
    "critical": "#ef4444",
}

DEFAULT_DISCLAIMER = (
    "This report provides educational insights and clinical associations only. "
    "It is not a diagnosis or treatment recommendation. "
    "Please consult a qualified physician."
)


class PDFGenerationError(Exception):
    """Raised when PDF generation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def generate_pdf(
    analysis: dict, charts: dict, job_id: str, language: str = "en"
) -> str:
    """Generate a PDF report from analysis data and charts.

    Args:
        analysis: Structured analysis dict from LLM (translated if Urdu).
        charts: Dict from chart_generator: { category_index: { "bar": path, "gauges": [paths] } }
        job_id: Job identifier for output path.
        language: Report language ("en" or "ur"). Urdu uses RTL layout.

    Returns:
        Path to the generated PDF file.

    Raises:
        PDFGenerationError: If PDF generation fails.
    """
    settings = get_settings()
    output_dir = Path(settings.outputs_path) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = str(output_dir / "report.pdf")

    try:
        # Load Jinja2 template
        if not TEMPLATES_DIR.exists():
            raise PDFGenerationError(
                f"Templates directory not found: {TEMPLATES_DIR}"
            )

        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template("report.html")

        # Read CSS inline
        css_path = TEMPLATES_DIR / "styles.css"
        css_content = ""
        if css_path.exists():
            css_content = css_path.read_text(encoding="utf-8")

        # Prepare template context
        is_rtl = language == "ur"
        context = {
            "analysis": analysis,
            "charts": charts,
            "css_content": css_content,
            "severity_colors": SEVERITY_COLORS,
            "disclaimer": analysis.get("disclaimer", DEFAULT_DISCLAIMER),
            "language": language,
            "is_rtl": is_rtl,
        }

        # Render HTML
        try:
            html_content = template.render(**context)
        except Exception as e:
            logger.exception(f"Template rendering failed for job {job_id}")
            raise PDFGenerationError(
                "PDF generation failed - template rendering error. "
                "The analysis data may have unexpected formatting."
            )

        # Generate PDF with WeasyPrint
        try:
            html_doc = HTML(string=html_content, base_url=str(TEMPLATES_DIR))
            html_doc.write_pdf(pdf_path)
        except Exception as e:
            logger.exception(f"WeasyPrint PDF generation failed for job {job_id}")
            raise PDFGenerationError(
                "PDF generation failed - unable to create PDF document. "
                "This may be due to font rendering issues."
            )

        logger.info(f"PDF generated: {pdf_path}")
        return pdf_path

    except PDFGenerationError:
        raise
    except Exception as e:
        logger.exception(f"PDF generation failed for job {job_id}")
        raise PDFGenerationError(f"PDF generation failed - unexpected error: {type(e).__name__}")
