#!/usr/bin/env python3
from __future__ import annotations

import html
import os
import smtplib
import sqlite3
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("BOOKING_DB", BASE_DIR / "bookings.db"))


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cognome TEXT NOT NULL,
                telefono TEXT NOT NULL,
                email TEXT NOT NULL,
                data_ora TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def send_confirmation_email(payload: dict[str, str]) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "")
    extra_notify = os.getenv("SMTP_NOTIFY")

    if not (smtp_host and smtp_user and smtp_pass and smtp_from):
        return False

    message = EmailMessage()
    message["Subject"] = "Conferma prenotazione"
    message["From"] = smtp_from
    message["To"] = payload["email"]
    if extra_notify:
        message["Bcc"] = extra_notify

    note_text = payload.get("note") or "Nessuna nota."
    message.set_content(
        "\n".join(
            [
                "Grazie per la tua richiesta di prenotazione.",
                "",
                f"Nome: {payload['nome']} {payload['cognome']}",
                f"Telefono: {payload['telefono']}",
                f"Email: {payload['email']}",
                f"Data e ora: {payload['data_ora']}",
                f"Note: {note_text}",
                "",
                "Ti contatteremo a breve per confermare.",
            ]
        )
    )

    if smtp_port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(smtp_user, smtp_pass)
            server.send_message(message)

    return True


class BookingHandler(BaseHTTPRequestHandler):
    def _send_text(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File non trovato")
            return

        content = path.read_bytes()
        content_type = "text/html; charset=utf-8"
        if path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif path.suffix in {".jpg", ".jpeg"}:
            content_type = "image/jpeg"
        elif path.suffix == ".png":
            content_type = "image/png"
        elif path.suffix == ".webp":
            content_type = "image/webp"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        requested = unquote(parsed.path)

        if requested in {"", "/"}:
            self._send_file(BASE_DIR / "index.html")
            return

        if requested == "/index.html":
            self._send_file(BASE_DIR / "index.html")
            return

        if requested.startswith("/public/"):
            self._send_file(BASE_DIR / requested.lstrip("/"))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path != "/prenota":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        data = {k: v[0] for k, v in parse_qs(raw).items()}

        required_fields = ["nome", "cognome", "telefono", "email", "data_ora", "privacy"]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            self._send_text("<h1>Dati mancanti</h1><p>Compila tutti i campi obbligatori.</p>", status=400)
            return

        payload = {
            "nome": data["nome"].strip(),
            "cognome": data["cognome"].strip(),
            "telefono": data["telefono"].strip(),
            "email": data["email"].strip(),
            "data_ora": data["data_ora"].strip(),
            "note": data.get("note", "").strip(),
        }

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO bookings (nome, cognome, telefono, email, data_ora, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["nome"],
                    payload["cognome"],
                    payload["telefono"],
                    payload["email"],
                    payload["data_ora"],
                    payload["note"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        email_sent = False
        try:
            email_sent = send_confirmation_email(payload)
        except Exception:
            email_sent = False

        safe_name = html.escape(f"{payload['nome']} {payload['cognome']}")
        email_status = (
            "Conferma inviata via email."
            if email_sent
            else "Prenotazione salvata. Configura SMTP per inviare la conferma."
        )
        body = f"""
        <!doctype html>
        <html lang="it">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Prenotazione ricevuta</title>
            <style>
              body {{ font-family: Arial, sans-serif; padding: 40px; background: #f8fafc; color: #0b0f1a; }}
              .card {{ max-width: 520px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 24px; }}
              a {{ color: #0b0f1a; }}
            </style>
          </head>
          <body>
            <div class="card">
              <h1>Grazie, {safe_name}.</h1>
              <p>La tua richiesta e stata registrata.</p>
              <p><strong>{html.escape(email_status)}</strong></p>
              <p><a href="/">Torna alla pagina principale</a></p>
            </div>
          </body>
        </html>
        """
        self._send_text(body)


def run() -> None:
    init_db()
    host = os.getenv("BOOKING_HOST", "127.0.0.1")
    port = int(os.getenv("BOOKING_PORT", "8000"))
    server = HTTPServer((host, port), BookingHandler)
    print(f"Server avviato su http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
