"""Write docs/UNIVAC_1218_Instruction_Table.xlsx from the instruction catalog."""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from u1218.repertoire import CATALOG

COLUMNS = ("Code", "Format", "Mnemonic", "Instruction", "Card description", "Emulator operation",
           "Category", "Time (usec)", "SR sensitive", "B modified", "Notes")
WIDTHS = (8, 7, 10, 34, 52, 52, 13, 11, 8, 8, 28)


def main(path: Path = ROOT / "docs" / "UNIVAC_1218_Instruction_Table.xlsx") -> Path:
    book = Workbook()
    sheet = book.active
    sheet.title = "Repertoire"
    sheet.append(COLUMNS)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="3E4452")
        cell.alignment = Alignment(vertical="center")
    for e in sorted(CATALOG, key=lambda e: (e.f, -1 if e.m is None else e.m)):
        sheet.append((e.code, e.format, e.mnemonic, e.name, e.card, e.pseudo, e.category,
                      e.time, "#" if e.sr else "", "*" if e.b_mod else "", e.notes))
    for index, width in enumerate(WIDTHS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    book.save(path)
    return path


if __name__ == "__main__":
    print(main())
