# Python coursework pipeline

This folder contains the Python implementation of the payment checking prototype:

- extracting text from PDF bank receipts;
- preprocessing receipt photos and screenshots before OCR;
- recognizing image text through local Tesseract OCR;
- extracting key payment attributes;
- checking one uploaded document against manually entered expected details;
- batch matching a CSV/XLSX table of expected payments against a set of bank documents;
- calculating a fuzzy matching score;
- exporting CSV and XLSX results.

Run the local web interface:

```powershell
python python_coursework\local_webapp.py
```

Or use:

```text
run_localhost_app.bat
```

Then open:

```text
http://127.0.0.1:8000
```

Statuses returned by the system:

- `Оплачено`;
- `Возможное совпадение`;
- `Не оплачено`.

For image OCR, install Tesseract OCR separately or set `TESSERACT_CMD` to the full path of `tesseract.exe`.
