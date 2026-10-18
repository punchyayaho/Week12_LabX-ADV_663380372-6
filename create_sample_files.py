# create_sample_files.py
"""Creates the sample attachments: data/reports/sales_report.pdf and data/reports/summary_data.xlsx."""
import datetime
import os

import openpyxl
from openpyxl.styles import Font
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

REPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reports")
os.makedirs(REPORTS, exist_ok=True)

c = canvas.Canvas(os.path.join(REPORTS, "sales_report.pdf"), pagesize=A4)
c.setFont("Helvetica-Bold", 20)
c.drawString(72, 770, "Daily Sales Summary")
c.setFont("Helvetica", 12)
c.drawString(72, 745, f"Date: {datetime.date.today().isoformat()}")
c.drawString(72, 725, "Total sales: $12,345.67")
c.drawString(72, 705, "Total active customers: 500")
c.save()

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Summary"
for row in [["Region", "Sales", "Customers"], ["North", 4200.50, 160], ["South", 3100.17, 120],
            ["East", 2800.00, 110], ["West", 2245.00, 110], ["Total", 12345.67, 500]]:
    ws.append(row)
for cell in ws[1]:
    cell.font = Font(bold=True)
wb.save(os.path.join(REPORTS, "summary_data.xlsx"))
print("Created data/reports/sales_report.pdf and data/reports/summary_data.xlsx")
