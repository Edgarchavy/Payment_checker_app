from __future__ import annotations

from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import cgi
import os
import shutil

from check_pipeline.field_extractor import extract_from_pdf, extract_from_text
from check_pipeline.manual_match import ManualExpectation, check_payment
from check_pipeline.ocr_tesseract import extract_text_with_tesseract


ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "project_output_py" / "web_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
      max-width: 980px;
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
    h1, h2 {{
      margin-top: 0;
    }}
    .lead {{
      color: var(--muted);
      margin-bottom: 24px;
    }}
    form {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px 20px;
    }}
    label {{
      display: block;
      font-size: 14px;
      margin-bottom: 6px;
      color: var(--muted);
    }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 16px;
      background: #fff;
    }}
    .full {{
      grid-column: 1 / -1;
    }}
    .actions {{
      grid-column: 1 / -1;
      display: flex;
      gap: 12px;
      align-items: center;
      margin-top: 8px;
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
    .note {{
      color: var(--muted);
      font-size: 14px;
    }}
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
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }}
    .panel {{
      background: white;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
    }}
    dl {{
      margin: 0;
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 10px 14px;
    }}
    dt {{
      color: var(--muted);
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #fbf7ef;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      font-size: 14px;
    }}
    .back {{
      display: inline-block;
      margin-top: 18px;
      color: var(--accent);
      text-decoration: none;
      font-weight: bold;
    }}
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


FORM_HTML = """
<h1>Проверка оплаты</h1>
<p class="lead">Укажи, что именно должно быть оплачено, затем загрузи PDF, фото или скриншот чека. Система извлечет реквизиты и проверит, соответствует ли документ ожиданию.</p>
<form method="post" enctype="multipart/form-data">
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
    <input name="expected_recipient_name" placeholder="Например: UNIVERSAM" required>
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
    <input type="file" name="receipt_file" accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp" required>
  </div>
  <div class="actions">
    <button type="submit">Проверить оплату</button>
  </div>
</form>
"""


class ReceiptAppHandler(BaseHTTPRequestHandler):
    server_version = "ReceiptCheckApp/1.0"

    def do_GET(self) -> None:
        self._send_html(render_page(FORM_HTML))

    def do_POST(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )

        uploaded = form["receipt_file"] if "receipt_file" in form else None
        if uploaded is None or not getattr(uploaded, "filename", ""):
            self._send_html(render_page("<h1>Ошибка</h1><p>Файл не был загружен.</p>" + FORM_HTML), status=HTTPStatus.BAD_REQUEST)
            return

        safe_name = Path(uploaded.filename).name
        saved_path = UPLOAD_DIR / safe_name
        with saved_path.open("wb") as handle:
            shutil.copyfileobj(uploaded.file, handle)

        expectation = ManualExpectation(
            expected_amount=form.getfirst("expected_amount", "").strip(),
            expected_currency=form.getfirst("expected_currency", "BYN").strip(),
            expected_recipient_name=form.getfirst("expected_recipient_name", "").strip(),
            expected_receipt_type=form.getfirst("expected_receipt_type", "").strip(),
            expected_payer_name=form.getfirst("expected_payer_name", "").strip(),
            expected_reference_code=form.getfirst("expected_reference_code", "").strip(),
        )

        try:
            suffix = saved_path.suffix.lower()
            if suffix == ".pdf":
                document = extract_from_pdf(saved_path)
            else:
                text = extract_text_with_tesseract(saved_path)
                document = extract_from_text(text, source_path=str(saved_path), file_name=safe_name)

            result = check_payment(document, expectation)
            body = self._result_html(expectation, document, result)
            self._send_html(render_page(body))
        except Exception as exc:
            body = f"""
            <h1>Ошибка обработки</h1>
            <p class="lead">Не удалось обработать документ: <strong>{escape(str(exc))}</strong></p>
            {FORM_HTML}
            """
            self._send_html(render_page(body), status=HTTPStatus.INTERNAL_SERVER_ERROR)

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

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = html.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    host = os.environ.get("RECEIPT_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("RECEIPT_APP_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ReceiptAppHandler)
    print(f"Open http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
