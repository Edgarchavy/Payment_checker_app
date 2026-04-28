# Python coursework pipeline

This folder contains a Python implementation for:
- extracting text from Alfa-Bank PDF receipts
- parsing key payment fields
- building a reference table of expected payments
- matching actual checks against expected values
- exporting CSV and XLSX outputs

Main command:

```powershell
python python_coursework\main.py run-all
```

Optional image OCR:
- use `python_coursework/check_pipeline/ocr_tesseract.py`
- requires local Tesseract OCR installation
- intended for receipt photos or scans

Outputs are written to:
- `project_output_py/01_extracted`
- `project_output_py/02_reference`
- `project_output_py/03_results`

Local web interface:

```powershell
python python_coursework\local_webapp.py
```

Or on Windows you can simply run:

```text
run_localhost_app.bat
```

Then open:

```text
http://127.0.0.1:8000
```

In the browser you can:
- enter the expected amount
- enter recipient and optional payment code
- upload a PDF receipt
- upload a receipt photo or screenshot if Tesseract OCR is installed
- receive a verdict: `Оплачено`, `Частично оплачено`, or `Не оплачено`
