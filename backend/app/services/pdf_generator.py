"""
DataForge – Pure Standard Library PDF 1.4 Invoice Generator.
Complies with ISO 32000-1 (PDF Standard).
Zero third-party library dependencies (no reportlab, no weasyprint).
Produces vector graphics, crisp typography (Helvetica, Helvetica-Bold), and exact accounting tables.
"""

import io
from datetime import datetime, timezone
from typing import Dict, Any, List


class PDFCanvas:
    """
    Minimalist PDF 1.4 canvas for vector graphics and typography.
    Page dimensions: A4 (595.28 pt width x 841.89 pt height).
    Coordinate system: Origin (0,0) is bottom-left.
    """

    def __init__(self, width: float = 595.28, height: float = 841.89):
        self.width = width
        self.height = height
        self.stream = io.BytesIO()

    def set_fill_color(self, r: float, g: float, b: float):
        """Sets non-stroking (fill) color (0.0 to 1.0)."""
        self.stream.write(f"{r:.3f} {g:.3f} {b:.3f} rg\n".encode("latin1"))

    def set_stroke_color(self, r: float, g: float, b: float):
        """Sets stroking color (0.0 to 1.0)."""
        self.stream.write(f"{r:.3f} {g:.3f} {b:.3f} RG\n".encode("latin1"))

    def set_line_width(self, width: float):
        """Sets line stroke width in points."""
        self.stream.write(f"{width:.2f} w\n".encode("latin1"))

    def rect(self, x: float, y: float, w: float, h: float, fill: bool = True, stroke: bool = False):
        """Draws a rectangle at (x, y) with width w and height h."""
        op = "B" if (fill and stroke) else ("f" if fill else "S")
        self.stream.write(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re {op}\n".encode("latin1"))

    def line(self, x1: float, y1: float, x2: float, y2: float):
        """Draws a straight line from (x1, y1) to (x2, y2)."""
        self.stream.write(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S\n".encode("latin1"))

    def draw_text(self, text: str, x: float, y: float, font: str = "/F1", size: float = 10):
        """
        Draws text string at (x, y).
        Standard fonts: /F1 (Helvetica), /F2 (Helvetica-Bold), /F3 (Courier).
        """
        escaped = (
            str(text)
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .encode("latin1", errors="replace")
            .decode("latin1")
        )
        self.stream.write(
            f"BT {font} {size:.1f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj ET\n".encode("latin1")
        )

    def get_content_stream_bytes(self) -> bytes:
        return self.stream.getvalue()


class PDFInvoiceGenerator:
    """
    Renders enterprise commercial billing invoices for DataForge customer tenants.
    """

    @classmethod
    def generate(cls, invoice_data: Dict[str, Any]) -> bytes:
        canvas = PDFCanvas(width=595.28, height=841.89)

        # 1. Background / Header Top Bar
        # Slate top header bar (DataForge dark theme accent)
        canvas.set_fill_color(0.06, 0.09, 0.16)  # Dark slate #0f172a
        canvas.rect(0, 770, 595.28, 71.89, fill=True, stroke=False)

        # Brand Logo Text
        canvas.set_fill_color(0.24, 0.51, 0.96)  # Brand Blue #3b82f6
        canvas.draw_text("DATAFORGE", 40, 805, font="/F2", size=20)
        canvas.set_fill_color(0.58, 0.65, 0.75)  # Light Slate
        canvas.draw_text("ENTERPRISE PLATFORM", 175, 807, font="/F1", size=10)

        canvas.set_fill_color(0.94, 0.96, 0.98)  # White/Slate
        canvas.draw_text("COMMERCIAL TAX INVOICE", 380, 805, font="/F2", size=13)
        canvas.set_fill_color(0.58, 0.65, 0.75)
        canvas.draw_text("Original for Recipient", 445, 788, font="/F1", size=9)

        # 2. Company & Invoice Info Header Section
        canvas.set_fill_color(0.12, 0.16, 0.24)
        canvas.draw_text("ISSUED BY:", 40, 745, font="/F2", size=9)
        canvas.set_fill_color(0.25, 0.30, 0.38)
        canvas.draw_text("DataForge Cloud Technologies Pvt. Ltd.", 40, 730, font="/F2", size=10)
        canvas.draw_text("Plot 42, Outer Ring Road, Bellandur", 40, 717, font="/F1", size=9)
        canvas.draw_text("Bangalore, KA 560103, India", 40, 705, font="/F1", size=9)
        canvas.draw_text("GSTIN: 29AABCD1234F1Z5 | PAN: AABCD1234F", 40, 693, font="/F1", size=9)
        canvas.draw_text("billing@dataforge.io | https://dataforge.io", 40, 681, font="/F1", size=9)

        # Invoice Metadata Box (Right Side)
        canvas.set_fill_color(0.96, 0.97, 0.99)
        canvas.set_stroke_color(0.85, 0.88, 0.93)
        canvas.set_line_width(0.8)
        canvas.rect(340, 665, 215, 92, fill=True, stroke=True)

        canvas.set_fill_color(0.12, 0.16, 0.24)
        canvas.draw_text("Invoice No:", 350, 742, font="/F2", size=9)
        canvas.draw_text(invoice_data.get("invoice_number", "DF-INV-XXXX"), 425, 742, font="/F3", size=9)

        canvas.draw_text("Billing Period:", 350, 726, font="/F1", size=9)
        canvas.draw_text(invoice_data.get("period_key", "2026-11"), 425, 726, font="/F1", size=9)

        canvas.draw_text("Issue Date:", 350, 710, font="/F1", size=9)
        issue_date_str = str(invoice_data.get("issue_date", ""))[:10]
        canvas.draw_text(issue_date_str or "2026-11-01", 425, 710, font="/F1", size=9)

        canvas.draw_text("Due Date:", 350, 694, font="/F1", size=9)
        due_date_str = str(invoice_data.get("due_date", ""))[:10]
        canvas.draw_text(due_date_str or "2026-11-15", 425, 694, font="/F1", size=9)

        canvas.draw_text("Status:", 350, 676, font="/F2", size=9)
        status = invoice_data.get("status", "Issued").upper()
        if status == "PAID":
            canvas.set_fill_color(0.05, 0.60, 0.35)  # Emerald green
        else:
            canvas.set_fill_color(0.80, 0.40, 0.10)  # Amber
        canvas.draw_text(status, 425, 676, font="/F2", size=10)

        # 3. Bill To Section
        canvas.set_fill_color(0.96, 0.97, 0.99)
        canvas.set_stroke_color(0.85, 0.88, 0.93)
        canvas.rect(40, 580, 515, 72, fill=True, stroke=True)

        canvas.set_fill_color(0.12, 0.16, 0.24)
        canvas.draw_text("BILLED TO (CUSTOMER TENANT):", 52, 638, font="/F2", size=9)
        canvas.draw_text(invoice_data.get("tenant_name", "Enterprise Tenant"), 52, 622, font="/F2", size=11)

        canvas.set_fill_color(0.35, 0.40, 0.50)
        email = invoice_data.get("billing_email", "billing@customer.com")
        canvas.draw_text(f"Email: {email}", 52, 608, font="/F1", size=9)
        tax_id = invoice_data.get("tax_identifier") or "Unregistered / Standard B2B"
        canvas.draw_text(f"GSTIN / Tax ID: {tax_id}", 52, 594, font="/F1", size=9)

        model = invoice_data.get("deployment_model", "BYOC - Self Hosted Single Tenant")
        canvas.draw_text(f"Deployment Model: {model}", 320, 608, font="/F1", size=9)
        currency = invoice_data.get("currency", "INR")
        canvas.draw_text(f"Currency: {currency}", 320, 594, font="/F1", size=9)

        # 4. Itemized Line Items Table
        table_top = 550
        canvas.set_fill_color(0.12, 0.16, 0.24)  # Dark header background
        canvas.rect(40, table_top - 20, 515, 22, fill=True, stroke=False)

        # Table Column Headers
        canvas.set_fill_color(0.98, 0.98, 0.98)
        canvas.draw_text("ITEM DESCRIPTION", 50, table_top - 14, font="/F2", size=8.5)
        canvas.draw_text("TYPE", 270, table_top - 14, font="/F2", size=8.5)
        canvas.draw_text("QTY", 370, table_top - 14, font="/F2", size=8.5)
        canvas.draw_text("RATE (INR)", 420, table_top - 14, font="/F2", size=8.5)
        canvas.draw_text("AMOUNT (INR)", 480, table_top - 14, font="/F2", size=8.5)

        # Render Rows
        current_y = table_top - 38
        line_items = invoice_data.get("line_items", [])
        if not line_items:
            # Default fallback line item if none explicitly passed
            line_items = [
                {
                    "description": "DataForge Platform Subscription",
                    "item_type": "SubscriptionBase",
                    "quantity": 1,
                    "unit_price": invoice_data.get("subscription_amount", 9999.0),
                    "amount": invoice_data.get("subscription_amount", 9999.0)
                }
            ]

        for i, item in enumerate(line_items):
            # Alternating subtle row background
            if i % 2 == 1:
                canvas.set_fill_color(0.98, 0.98, 0.99)
                canvas.rect(40, current_y - 5, 515, 18, fill=True, stroke=False)

            canvas.set_fill_color(0.15, 0.20, 0.28)
            desc = str(item.get("description", ""))[:42]
            canvas.draw_text(desc, 50, current_y, font="/F1", size=8.5)

            itype = str(item.get("item_type", ""))[:18]
            canvas.draw_text(itype, 270, current_y, font="/F1", size=8)

            qty = item.get("quantity", 1)
            canvas.draw_text(f"{qty:,.0f}" if isinstance(qty, (int, float)) and qty.is_integer() else f"{qty:,.2f}", 370, current_y, font="/F1", size=8.5)

            unit_price = item.get("unit_price", 0.0)
            canvas.draw_text(f"{unit_price:,.2f}", 420, current_y, font="/F1", size=8.5)

            amt = item.get("amount", 0.0)
            canvas.draw_text(f"{amt:,.2f}", 485, current_y, font="/F2", size=8.5)

            current_y -= 20

        # Horizontal separator line
        canvas.set_stroke_color(0.80, 0.84, 0.90)
        canvas.set_line_width(0.7)
        canvas.line(40, current_y + 10, 555, current_y + 10)

        # 5. Financial Summary Calculation Box
        summary_top = current_y - 10
        canvas.set_fill_color(0.96, 0.97, 0.99)
        canvas.set_stroke_color(0.85, 0.88, 0.93)
        canvas.rect(320, summary_top - 105, 235, 110, fill=True, stroke=True)

        canvas.set_fill_color(0.20, 0.25, 0.35)
        canvas.draw_text("Subtotal:", 332, summary_top - 15, font="/F1", size=9)
        subtotal = float(invoice_data.get("subtotal_amount", 0.0))
        canvas.draw_text(f"INR {subtotal:,.2f}", 470, summary_top - 15, font="/F2", size=9)

        # GST breakdown (CGST 9% + SGST 9% or IGST 18%)
        tax_pct = float(invoice_data.get("tax_percent", 18.00))
        tax_amt = float(invoice_data.get("tax_amount", 0.0))
        cgst = tax_amt / 2.0
        sgst = tax_amt / 2.0

        canvas.draw_text(f"CGST ({(tax_pct/2.0):.1f}%):", 332, summary_top - 32, font="/F1", size=8.5)
        canvas.draw_text(f"INR {cgst:,.2f}", 470, summary_top - 32, font="/F1", size=8.5)

        canvas.draw_text(f"SGST ({(tax_pct/2.0):.1f}%):", 332, summary_top - 48, font="/F1", size=8.5)
        canvas.draw_text(f"INR {sgst:,.2f}", 470, summary_top - 48, font="/F1", size=8.5)

        adj = float(invoice_data.get("adjustments_amount", 0.0))
        if adj != 0:
            canvas.draw_text("Adjustments / Credits:", 332, summary_top - 64, font="/F1", size=8.5)
            canvas.draw_text(f"- INR {adj:,.2f}", 470, summary_top - 64, font="/F1", size=8.5)

        # Total Payable Box
        canvas.set_fill_color(0.12, 0.16, 0.24)
        canvas.rect(320, summary_top - 105, 235, 26, fill=True, stroke=False)
        canvas.set_fill_color(0.98, 0.98, 0.98)
        canvas.draw_text("TOTAL PAYABLE:", 332, summary_top - 93, font="/F2", size=9.5)
        total = float(invoice_data.get("total_amount", subtotal + tax_amt - adj))
        canvas.draw_text(f"INR {total:,.2f}", 455, summary_top - 93, font="/F2", size=11)

        # 6. Payment Remittance Details (Left Side)
        canvas.set_fill_color(0.15, 0.20, 0.30)
        canvas.draw_text("BANK REMITTANCE & PAYMENT DETAILS:", 40, summary_top - 15, font="/F2", size=8.5)
        canvas.set_fill_color(0.35, 0.40, 0.50)
        canvas.draw_text("Bank Name: HDFC Bank Limited (Corporate Banking)", 40, summary_top - 30, font="/F1", size=8.5)
        canvas.draw_text("Beneficiary: DataForge Cloud Technologies Pvt Ltd", 40, summary_top - 44, font="/F1", size=8.5)
        canvas.draw_text("Account Number: 50200084729104 (Current)", 40, summary_top - 58, font="/F1", size=8.5)
        canvas.draw_text("IFSC Code: HDFC0000240 | SWIFT: HDFCINBBXXX", 40, summary_top - 72, font="/F1", size=8.5)
        canvas.draw_text("Reference: Please cite Invoice Number on transfer receipt.", 40, summary_top - 86, font="/F1", size=8)

        # 7. Terms & Declarations
        terms_y = 100
        canvas.set_stroke_color(0.85, 0.88, 0.93)
        canvas.line(40, terms_y + 15, 555, terms_y + 15)

        canvas.set_fill_color(0.40, 0.45, 0.55)
        canvas.draw_text("Terms & Conditions:", 40, terms_y, font="/F2", size=8)
        canvas.draw_text("1. All fees billed under DataForge Master Enterprise Services Agreement. Payments due within 15 days of issue.", 40, terms_y - 12, font="/F1", size=7.5)
        canvas.draw_text("2. Pipeline execution allowances reset on the 1st of each calendar month. Unused runs do not roll over.", 40, terms_y - 23, font="/F1", size=7.5)
        canvas.draw_text("3. BYOC Mode: DataForge charges zero markup on customer cloud compute (AWS, Azure, GCP).", 40, terms_y - 34, font="/F1", size=7.5)
        canvas.draw_text("4. Computer generated digital invoice. Requires no physical signature under Indian Information Technology Act.", 40, terms_y - 45, font="/F1", size=7.5)

        # 8. Bottom Footer
        canvas.set_fill_color(0.06, 0.09, 0.16)
        canvas.rect(0, 0, 595.28, 28, fill=True, stroke=False)
        canvas.set_fill_color(0.60, 0.65, 0.75)
        canvas.draw_text("DataForge – Cloud-Agnostic Enterprise Data Integration Platform | www.dataforge.io", 110, 10, font="/F1", size=8)

        # Assemble PDF 1.4 objects
        content_stream = canvas.get_content_stream_bytes()
        stream_len = len(content_stream)

        pdf = io.BytesIO()
        pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets = []

        # Object 1: Catalog
        offsets.append(pdf.tell())
        pdf.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Object 2: Pages
        offsets.append(pdf.tell())
        pdf.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

        # Object 3: Page
        offsets.append(pdf.tell())
        page_obj = (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] "
            b"/Resources << /Font << "
            b"/F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
            b"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
            b"/F3 << /Type /Font /Subtype /Type1 /BaseFont /Courier >> >> >> "
            b"/Contents 4 0 R >>\nendobj\n"
        )
        pdf.write(page_obj)

        # Object 4: Content Stream
        offsets.append(pdf.tell())
        pdf.write(f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin1"))
        pdf.write(content_stream)
        pdf.write(b"\nendstream\nendobj\n")

        # Cross-reference table
        xref_offset = pdf.tell()
        pdf.write(b"xref\n0 5\n0000000000 65535 f \n")
        for offset in offsets:
            pdf.write(f"{offset:010d} 00000 n \n".encode("latin1"))

        # Trailer
        pdf.write(
            f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin1")
        )

        return pdf.getvalue()
