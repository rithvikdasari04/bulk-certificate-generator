"""Create an individual PDF certificate using the built-in template."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "generated_certificates"
CERTIFICATE_TITLE = "Certificate of Internship Completion"


def generate_certificate(full_name: str, output_dir: Path | None = None) -> str:
    """Render a certificate and return its safe, unique filename."""
    destination = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    destination.mkdir(parents=True, exist_ok=True)

    # Render fully in memory first so a rendering failure does not leave a PDF
    # that looks complete but is only partially written.
    pdf_buffer = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(
        pdf_buffer, pagesize=(page_width, page_height), pageCompression=0
    )

    pdf.setFillColor(colors.HexColor("#F7F8FA"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#17365D"))
    pdf.setLineWidth(3)
    pdf.roundRect(30, 30, page_width - 60, page_height - 60, 12, fill=0)
    pdf.setStrokeColor(colors.HexColor("#C69C3A"))
    pdf.setLineWidth(1)
    pdf.roundRect(40, 40, page_width - 80, page_height - 80, 8, fill=0)

    pdf.setFillColor(colors.HexColor("#17365D"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(page_width / 2, page_height - 140, CERTIFICATE_TITLE.upper())
    pdf.setFillColor(colors.HexColor("#4B5563"))
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(page_width / 2, page_height - 195, "This certificate is proudly presented to")

    # Fit long names inside the decorative frame while keeping them readable.
    name_size = 30
    while name_size > 16 and stringWidth(full_name, "Helvetica-Bold", name_size) > page_width - 140:
        name_size -= 1
    pdf.setFillColor(colors.HexColor("#17365D"))
    pdf.setFont("Helvetica-Bold", name_size)
    pdf.drawCentredString(page_width / 2, page_height / 2 + 5, full_name)

    pdf.setFillColor(colors.HexColor("#4B5563"))
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(page_width / 2, page_height / 2 - 35, "for the successful completion of the internship program")
    pdf.setStrokeColor(colors.HexColor("#C69C3A"))
    pdf.setLineWidth(1)
    pdf.line(page_width / 2 - 105, 105, page_width / 2 + 105, 105)
    pdf.setFillColor(colors.HexColor("#17365D"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(page_width / 2, 85, "INTERNSHIP PROGRAM")
    pdf.showPage()
    pdf.save()

    filename = f"{uuid4().hex}.pdf"
    final_path = destination / filename
    temporary_path = destination / f".{uuid4().hex}.tmp"
    try:
        temporary_path.write_bytes(pdf_buffer.getvalue())
        temporary_path.replace(final_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return filename
