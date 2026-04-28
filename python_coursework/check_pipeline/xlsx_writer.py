from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape
import zipfile


def _column_name(index: int) -> str:
    name = ""
    value = index
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        name = chr(65 + remainder) + name
    return name


def write_xlsx(path: str | Path, rows: list[list[str]], widths: dict[int, int] | None = None, title: str = "Coursework output") -> None:
    path = Path(path)
    widths = widths or {}
    created = datetime(2026, 4, 26, 12, 0, 0).isoformat() + "Z"

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "_rels").mkdir(parents=True, exist_ok=True)
        (root / "xl" / "_rels").mkdir(parents=True, exist_ok=True)
        (root / "xl" / "worksheets").mkdir(parents=True, exist_ok=True)
        (root / "docProps").mkdir(parents=True, exist_ok=True)

        sheet_rows: list[str] = []
        for row_index, row in enumerate(rows, start=1):
            cell_xml: list[str] = []
            for col_index, value in enumerate(row, start=1):
                cell_ref = f"{_column_name(col_index)}{row_index}"
                style_id = 1 if row_index == 1 else 0
                escaped = escape(str(value))
                cell_xml.append(
                    f'<c r="{cell_ref}" t="inlineStr" s="{style_id}"><is><t xml:space="preserve">{escaped}</t></is></c>'
                )
            sheet_rows.append(f'<row r="{row_index}">{"".join(cell_xml)}</row>')

        cols_xml: list[str] = []
        total_cols = len(rows[0]) if rows else 0
        for idx in range(1, total_cols + 1):
            width = widths.get(idx, 18)
            cols_xml.append(f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>')

        sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>
    {' '.join(cols_xml)}
  </cols>
  <sheetData>
    {' '.join(sheet_rows)}
  </sheetData>
</worksheet>
"""

        workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""

        styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="2">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
  </fills>
  <borders count="1">
    <border><left/><right/><top/><bottom/><diagonal/></border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>
"""

        content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""

        workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

        app_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Excel</Application>
</Properties>
"""

        core_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>
"""

        (root / "[Content_Types].xml").write_text(content_types_xml, encoding="utf-8")
        (root / "_rels" / ".rels").write_text(rels_xml, encoding="utf-8")
        (root / "xl" / "workbook.xml").write_text(workbook_xml, encoding="utf-8")
        (root / "xl" / "_rels" / "workbook.xml.rels").write_text(workbook_rels_xml, encoding="utf-8")
        (root / "xl" / "worksheets" / "sheet1.xml").write_text(sheet_xml, encoding="utf-8")
        (root / "xl" / "styles.xml").write_text(styles_xml, encoding="utf-8")
        (root / "docProps" / "app.xml").write_text(app_xml, encoding="utf-8")
        (root / "docProps" / "core.xml").write_text(core_xml, encoding="utf-8")

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in root.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(root))
