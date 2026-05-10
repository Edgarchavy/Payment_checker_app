from __future__ import annotations

from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import cgi
import os
from urllib.parse import parse_qs, urlparse
import shutil
import time

from check_pipeline.entity_matching import (
    extract_document,
    match_expected_with_documents,
    read_expected_payments,
)
from check_pipeline.field_extractor import extract_from_pdf, extract_from_text
from check_pipeline.io_utils import ensure_dir, write_csv, write_json, write_xlsx_from_rows
from check_pipeline.manual_match import ManualExpectation, check_payment
from check_pipeline.ocr_tesseract import extract_text_with_tesseract


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "project_output_py"
UPLOAD_DIR = OUTPUT_DIR / "web_uploads"
BATCH_DIR = OUTPUT_DIR / "web_batch_results"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BATCH_DIR.mkdir(parents=True, exist_ok=True)


def render_page(body: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Проверка оплаты</title>
  <style>
    :root {{
      --bg: #f3efe6;
      --panel: #fffaf2;
      --ink: #1f2430;
      --muted: #6b7280;
      --accent: #0f766e;
      --accent-soft: #dff4ee;
      --danger: #b91c1c;
      --border: #dccfb8;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(135deg, #efe4cf 0%, #f7f1e8 45%, #e8f0eb 100%);
      color: var(--ink);
    }}
    .wrap {{
      max-width: 1100px;
      margin: 32px auto;
      padding: 0 20px 40px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 14px 40px rgba(63, 54, 42, 0.08);
    }}
    h1, h2, h3 {{ margin-top: 0; }}
    .lead {{ color: var(--muted); margin-bottom: 24px; }}
    .tabs {{ display: flex; gap: 10px; margin-bottom: 22px; flex-wrap: wrap; }}
    .tabs a {{
      text-decoration: none;
      border-radius: 999px;
      padding: 10px 16px;
      color: var(--accent);
      border: 1px solid var(--border);
      background: #fff;
      font-weight: bold;
    }}
    .tabs a.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    form {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px 20px; }}
    label {{ display: block; font-size: 14px; margin-bottom: 6px; color: var(--muted); }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 16px;
      background: #fff;
    }}
    .full {{ grid-column: 1 / -1; }}
    .actions {{
      grid-column: 1 / -1;
      display: flex;
      gap: 12px;
      align-items: center;
      margin-top: 8px;
      flex-wrap: wrap;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 12px 20px;
      background: var(--accent);
      color: white;
      font-size: 16px;
      cursor: pointer;
    }}
    .note {{ color: var(--muted); font-size: 14px; }}
    .status {{
      display: inline-block;
      padding: 8px 14px;
      border-radius: 999px;
      font-weight: bold;
      margin-bottom: 16px;
    }}
    .ok {{ background: #d1fae5; color: #065f46; }}
    .warn {{ background: #fef3c7; color: #92400e; }}
    .bad {{ background: #fee2e2; color: #991b1b; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    .panel {{
      background: white;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
    }}
    dl {{ margin: 0; display: grid; grid-template-columns: 180px 1fr; gap: 10px 14px; }}
    dt {{ color: var(--muted); }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #fbf7ef;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      font-size: 14px;
    }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 14px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 10px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: var(--accent-soft); color: var(--ink); }}
    .back, .download {{ display: inline-block; margin-top: 18px; color: var(--accent); text-decoration: none; font-weight: bold; }}
    @media (max-width: 760px) {{ form, .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      {body}
    </div>
  </div>
</body>
</html>"""


def nav(active: str) -> str:
    single = "active" if active == "single" else ""
    batch = "active" if active == "batch" else ""
    return f"""
    <div class="tabs">
      <a class="{single}" href="/">Одиночная проверка</a>
      <a class="{batch}" href="/batch">Пакетное сопоставление</a>
    </div>
    """


FORM_HTML = """
<h1>Проверка оплаты</h1>
<p class="lead">Укажи ожидаемые реквизиты и загрузи PDF, фото или скриншот чека. Система извлечет реквизиты и проверит соответствие.</p>
<form method="post" enctype="multipart/form-data" action="/check">
  <div>
    <label>Ожидаемая сумма</label>
    <input name="expected_amount" placeholder="Например: 105.55" required>
  </div>
  <div>
    <label>Валюта</label>
    <select name="expected_currency">
      <option>BYN</option>
      <option>USD</option>
      <option>EUR</option>
      <option>RUB</option>
    </select>
  </div>
  <div class="full">
    <label>Получатель платежа</label>
    <input name="expected_recipient_name" placeholder="Например: Главное управление" required>
  </div>
  <div>
    <label>Тип платежа</label>
    <select name="expected_receipt_type">
      <option value="">Любой</option>
      <option value="card_payment">card_payment</option>
      <option value="detailed_payment">detailed_payment</option>
      <option value="transfer_or_exchange">transfer_or_exchange</option>
      <option value="foreign_card_payment">foreign_card_payment</option>
      <option value="other">other</option>
    </select>
  </div>
  <div>
    <label>Плательщик</label>
    <input name="expected_payer_name" placeholder="Необязательно">
  </div>
  <div class="full">
    <label>Назначение платежа / RRN / MCC / код платежа</label>
    <input name="expected_reference_code" placeholder="Необязательно">
  </div>
  <div class="full">
    <label>Файл чека</label>
    <input type="file" name="receipt_file" accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff" required>
  </div>
  <div class="actions">
    <button type="submit">Проверить оплату</button>
  </div>
</form>
"""


BATCH_HTML = """
<h1>Пакетное сопоставление платежей</h1>
<p class="lead">Загрузи таблицу выставленных платежей и набор чеков. Система извлечет сущности из банковских документов и нечетко сопоставит их с ожидаемыми платежами.</p>
<form method="post" enctype="multipart/form-data" action="/batch">
  <div class="full">
    <label>Таблица ожидаемых платежей CSV или XLSX</label>
    <input type="file" name="expected_table" accept=".csv,.xlsx" required>
    <p class="note">Поддерживаемые колонки: payment_id, expected_amount, expected_currency, expected_payer_name, expected_recipient_name, expected_purpose, expected_date, expected_reference_code. Можно использовать и русские названия: сумма, валюта, плательщик, получатель, назначение, дата, код платежа.</p>
  </div>
  <div class="full">
    <label>Чеки PDF / фото / скриншоты</label>
    <input type="file" name="receipt_files" accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff" multiple required>
  </div>
  <div class="actions">
    <button type="submit">Сопоставить платежи</button>
    <span class="note">Сумма и получатель считаются критическими признаками.</span>
  </div>
</form>
"""


def safe_upload_name(filename: str) -> str:
    return f"{int(time.time() * 1000)}_{Path(filename).name}"


def save_upload(field) -> Path:
    saved_path = UPLOAD_DIR / safe_upload_name(field.filename)
    with saved_path.open("wb") as handle:
        shutil.copyfileobj(field.file, handle)
    return saved_path


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class ReceiptAppHandler(BaseHTTPRequestHandler):
    server_version = "ReceiptCheckApp/2.0"

    def do_GET(self) -> None:
        if self.path.startswith("/file"):
            self._send_file()
        elif self.path.startswith("/batch"):
            self._send_html(render_page(nav("batch") + BATCH_HTML))
        else:
            self._send_html(render_page(nav("single") + FORM_HTML))

    def do_POST(self) -> None:
        if self.path.startswith("/batch"):
            self._handle_batch()
        else:
            self._handle_single()

    def _read_form(self) -> cgi.FieldStorage:
        return cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )

    def _handle_single(self) -> None:
        form = self._read_form()
        uploaded = form["receipt_file"] if "receipt_file" in form else None
        if uploaded is None or not getattr(uploaded, "filename", ""):
            self._send_html(render_page(nav("single") + "<h1>Ошибка</h1><p>Файл не был загружен.</p>" + FORM_HTML), status=HTTPStatus.BAD_REQUEST)
            return

        saved_path = save_upload(uploaded)
        expectation = ManualExpectation(
            expected_amount=form.getfirst("expected_amount", "").strip(),
            expected_currency=form.getfirst("expected_currency", "BYN").strip(),
            expected_recipient_name=form.getfirst("expected_recipient_name", "").strip(),
            expected_receipt_type=form.getfirst("expected_receipt_type", "").strip(),
            expected_payer_name=form.getfirst("expected_payer_name", "").strip(),
            expected_reference_code=form.getfirst("expected_reference_code", "").strip(),
        )

        try:
            if saved_path.suffix.lower() == ".pdf":
                document = extract_from_pdf(saved_path)
            else:
                text = extract_text_with_tesseract(saved_path)
                document = extract_from_text(text, source_path=str(saved_path), file_name=Path(uploaded.filename).name)

            result = check_payment(document, expectation)
            body = self._result_html(expectation, document, result)
            self._send_html(render_page(nav("single") + body))
        except Exception as exc:
            body = f"""
            <h1>Ошибка обработки</h1>
            <p class="lead">Не удалось обработать документ: <strong>{escape(str(exc))}</strong></p>
            {FORM_HTML}
            """
            self._send_html(render_page(nav("single") + body), status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_batch(self) -> None:
        form = self._read_form()
        table_field = form["expected_table"] if "expected_table" in form else None
        receipt_fields = as_list(form["receipt_files"] if "receipt_files" in form else None)
        receipt_fields = [field for field in receipt_fields if getattr(field, "filename", "")]

        if table_field is None or not getattr(table_field, "filename", "") or not receipt_fields:
            self._send_html(render_page(nav("batch") + "<h1>Ошибка</h1><p>Нужно загрузить таблицу и хотя бы один чек.</p>" + BATCH_HTML), status=HTTPStatus.BAD_REQUEST)
            return

        try:
            table_path = save_upload(table_field)
            expected_rows = read_expected_payments(table_path)
            documents = []
            for field in receipt_fields:
                saved_path = save_upload(field)
                document = extract_document(saved_path)
                document.file_name = Path(field.filename).name
                documents.append(document)

            results = match_expected_with_documents(expected_rows, documents)
            result_dir = ensure_dir(BATCH_DIR / f"batch_{int(time.time())}")
            csv_path = result_dir / "entity_matching_results.csv"
            json_path = result_dir / "entity_matching_results.json"
            xlsx_path = result_dir / "entity_matching_results.xlsx"
            write_csv(csv_path, results)
            write_json(json_path, results)
            write_xlsx_from_rows(
                xlsx_path,
                results,
                widths={1: 18, 2: 20, 3: 12, 4: 34, 5: 14, 6: 14, 7: 12, 8: 12, 9: 28, 10: 28, 11: 34, 12: 34, 19: 42},
                title="Entity matching results",
            )

            self._send_html(render_page(nav("batch") + self._batch_result_html(results, csv_path, xlsx_path)))
        except Exception as exc:
            body = f"""
            <h1>Ошибка пакетного сопоставления</h1>
            <p class="lead">Не удалось выполнить сопоставление: <strong>{escape(str(exc))}</strong></p>
            {BATCH_HTML}
            """
            self._send_html(render_page(nav("batch") + body), status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _result_html(self, expectation: ManualExpectation, document, result) -> str:
        status_class = "ok" if result.status == "Оплачено" else "warn" if result.status == "Частично оплачено" else "bad"
        reason_labels = {
            "sum": "сумма",
            "currency": "валюта",
            "date": "дата",
            "recipient": "получатель",
            "type": "тип платежа",
            "payer": "плательщик",
            "payment_code": "код платежа",
        }
        reasons = ", ".join(reason_labels.get(item, item) for item in result.reasons) if result.reasons else "нет"
        return f"""
        <h1>Результат проверки</h1>
        <div class="status {status_class}">{escape(result.status)} — {escape(result.score)}</div>
        <div class="grid">
          <div class="panel">
            <h2>Ожидание</h2>
            <dl>
              <dt>Сумма</dt><dd>{escape(expectation.expected_amount)}</dd>
              <dt>Валюта</dt><dd>{escape(expectation.expected_currency)}</dd>
              <dt>Получатель</dt><dd>{escape(expectation.expected_recipient_name)}</dd>
              <dt>Тип</dt><dd>{escape(expectation.expected_receipt_type or "Любой")}</dd>
              <dt>Плательщик</dt><dd>{escape(expectation.expected_payer_name or "Не указан")}</dd>
              <dt>Код</dt><dd>{escape(expectation.expected_reference_code or "Не указан")}</dd>
            </dl>
          </div>
          <div class="panel">
            <h2>Из документа</h2>
            <dl>
              <dt>Файл</dt><dd>{escape(document.file_name)}</dd>
              <dt>Сумма</dt><dd>{escape(document.amount)}</dd>
              <dt>Валюта</dt><dd>{escape(document.currency)}</dd>
              <dt>Получатель</dt><dd>{escape(document.recipient_name)}</dd>
              <dt>Плательщик</dt><dd>{escape(document.payer_name)}</dd>
              <dt>Тип</dt><dd>{escape(document.receipt_type)}</dd>
              <dt>Дата</dt><dd>{escape(document.primary_datetime)}</dd>
              <dt>MCC</dt><dd>{escape(document.mcc_code)}</dd>
              <dt>RRN</dt><dd>{escape(document.rrn)}</dd>
              <dt>Reference</dt><dd>{escape(document.reference)}</dd>
            </dl>
          </div>
        </div>
        <div class="panel" style="margin-top:20px;">
          <h2>Причины расхождений</h2>
          <p>{escape(reasons)}</p>
        </div>
        <div class="panel" style="margin-top:20px;">
          <h2>Извлеченный текст</h2>
          <pre>{escape(document.full_text)}</pre>
        </div>
        <a class="back" href="/">Проверить другой документ</a>
        """

    def _batch_result_html(self, results, csv_path: Path, xlsx_path: Path) -> str:
        rows = []
        for result in results:
            status_class = "ok" if result.status == "оплачено" else "warn" if result.status == "возможное совпадение" else "bad"
            rows.append(f"""
            <tr>
              <td>{escape(result.payment_id)}</td>
              <td><span class="status {status_class}">{escape(result.status)}</span></td>
              <td>{escape(result.score)}</td>
              <td>{escape(result.matched_file or "не найден")}</td>
              <td>{escape(result.expected_amount)} / {escape(result.actual_amount)}</td>
              <td>{escape(result.expected_recipient_name)}<br><span class="note">{escape(result.actual_recipient_name)}</span></td>
              <td>{escape(result.mismatch_reasons)}</td>
            </tr>
            """)
        return f"""
        <h1>Результат пакетного сопоставления</h1>
        <p class="lead">Для каждого выставленного платежа выбран наиболее похожий чек. Итоговый score рассчитан нечетким алгоритмом по сумме, получателю, плательщику, назначению, дате и коду платежа.</p>
        <table>
          <thead>
            <tr>
              <th>Платеж</th>
              <th>Статус</th>
              <th>Score</th>
              <th>Чек</th>
              <th>Сумма</th>
              <th>Получатель</th>
              <th>Расхождения</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
        <p>
          <a class="download" href="/file?path={escape(str(csv_path))}">Скачать CSV</a>
          &nbsp;&nbsp;
          <a class="download" href="/file?path={escape(str(xlsx_path))}">Скачать XLSX</a>
        </p>
        <a class="back" href="/batch">Выполнить новое сопоставление</a>
        """

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = html.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        raw_path = query.get("path", [""])[0]
        try:
            path = Path(raw_path).resolve()
            allowed_root = BATCH_DIR.resolve()
            if allowed_root not in path.parents or not path.exists():
                raise FileNotFoundError("Файл недоступен")
            payload = path.read_bytes()
            content_type = "text/csv; charset=utf-8" if path.suffix.lower() == ".csv" else "application/octet-stream"
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self._send_html(render_page(nav("batch") + f"<h1>Ошибка</h1><p>{escape(str(exc))}</p>"), status=HTTPStatus.NOT_FOUND)


def main() -> None:
    host = os.environ.get("RECEIPT_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("RECEIPT_APP_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ReceiptAppHandler)
    print(f"Open http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
