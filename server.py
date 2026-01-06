#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import secrets
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
TIME_SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00"]


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
                data_ora TEXT,
                data TEXT,
                ora TEXT,
                note TEXT,
                status TEXT DEFAULT 'booked',
                token TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        columns = {row[1] for row in conn.execute("PRAGMA table_info(bookings)")}
        if "data" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN data TEXT")
        if "ora" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN ora TEXT")
        if "status" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'booked'")
        if "token" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN token TEXT")
        if "canceled_at" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN canceled_at TEXT")

        conn.execute("UPDATE bookings SET status = 'booked' WHERE status IS NULL")


def format_date_label(date_value: datetime) -> str:
    weekdays = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    months = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
    return f"{weekdays[date_value.weekday()]} {date_value.day:02d} {months[date_value.month - 1]}"


def fetch_availability(days: int = 60) -> dict:
    today = datetime.now(timezone.utc).date()
    date_keys = []
    for i in range(days):
        day = today.fromordinal(today.toordinal() + i)
        date_keys.append(day.isoformat())

    booked = {date_key: set() for date_key in date_keys}
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT data, ora
            FROM bookings
            WHERE status = 'booked' AND data IS NOT NULL AND ora IS NOT NULL
            """,
        ).fetchall()

    for row in rows:
        date_key, time_slot = row
        if date_key in booked:
            booked[date_key].add(time_slot)

    dates = []
    for date_key in date_keys:
        day = datetime.fromisoformat(date_key)
        available = [slot for slot in TIME_SLOTS if slot not in booked[date_key]]
        dates.append({"date": date_key, "label": format_date_label(day), "available": available})

    return {"dates": dates, "timeSlots": TIME_SLOTS, "minDate": date_keys[0], "maxDate": date_keys[-1]}


def send_confirmation_email(payload: dict[str, str], cancel_url: str) -> bool:
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
                "Se devi annullare la prenotazione, usa questo link:",
                cancel_url,
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

        if requested == "/api/availability":
            payload = fetch_availability()
            body = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if requested == "/annulla":
            query = parse_qs(parsed.query)
            token = query.get("token", [""])[0].strip()
            if not token:
                self._send_text("<h1>Token mancante</h1><p>Impossibile annullare.</p>", status=400)
                return

            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT id, status FROM bookings WHERE token = ?",
                    (token,),
                ).fetchone()
                if not row:
                    self._send_text("<h1>Token non valido</h1><p>Richiesta non trovata.</p>", status=404)
                    return

                booking_id, status = row
                if status == "canceled":
                    self._send_text("<h1>Prenotazione gia annullata</h1><p>Nessuna azione necessaria.</p>")
                    return

                conn.execute(
                    "UPDATE bookings SET status = 'canceled', canceled_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), booking_id),
                )

            self._send_text("<h1>Prenotazione annullata</h1><p>Lo slot e di nuovo disponibile.</p>")
            return

        if requested in {"", "/"}:
            self._send_file(BASE_DIR / "index.html")
            return

        if requested == "/index.html":
            self._send_file(BASE_DIR / "index.html")
            return

        if requested.startswith("/css/") or requested.startswith("/js/"):
            self._send_file(BASE_DIR / requested.lstrip("/"))
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

        required_fields = ["nome", "cognome", "telefono", "email", "data", "ora", "privacy"]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            self._send_text("<h1>Dati mancanti</h1><p>Compila tutti i campi obbligatori.</p>", status=400)
            return

        booking_date = data["data"].strip()
        booking_time = data["ora"].strip()
        data_ora = f"{booking_date} {booking_time}"

        today = datetime.now(timezone.utc).date()
        min_date = today
        max_date = today.fromordinal(today.toordinal() + 59)
        try:
            parsed_date = datetime.fromisoformat(booking_date).date()
        except ValueError:
            self._send_text("<h1>Data non valida</h1><p>Seleziona una data corretta.</p>", status=400)
            return

        if parsed_date < min_date or parsed_date > max_date:
            self._send_text("<h1>Data fuori intervallo</h1><p>Seleziona una data entro 2 mesi.</p>", status=400)
            return

        if booking_time not in TIME_SLOTS:
            self._send_text("<h1>Orario non valido</h1><p>Seleziona un orario valido.</p>", status=400)
            return
        token = secrets.token_urlsafe(24)
        payload = {
            "nome": data["nome"].strip(),
            "cognome": data["cognome"].strip(),
            "telefono": data["telefono"].strip(),
            "email": data["email"].strip(),
            "data_ora": data_ora,
            "note": data.get("note", "").strip(),
        }

        with sqlite3.connect(DB_PATH) as conn:
            exists = conn.execute(
                """
                SELECT 1 FROM bookings
                WHERE data = ? AND ora = ? AND status = 'booked'
                """,
                (booking_date, booking_time),
            ).fetchone()
            if exists:
                self._send_text("<h1>Slot non disponibile</h1><p>Seleziona un altro orario.</p>", status=409)
                return

            conn.execute(
                """
                INSERT INTO bookings (nome, cognome, telefono, email, data_ora, data, ora, note, status, token, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'booked', ?, ?)
                """,
                (
                    payload["nome"],
                    payload["cognome"],
                    payload["telefono"],
                    payload["email"],
                    payload["data_ora"],
                    booking_date,
                    booking_time,
                    payload["note"],
                    token,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        email_sent = False
        try:
            host = self.headers.get("Host", "127.0.0.1:8000")
            cancel_url = f"http://{host}/annulla?token={token}"
            email_sent = send_confirmation_email(payload, cancel_url)
        except Exception:
            email_sent = False

        safe_name = html.escape(f"{payload['nome']} {payload['cognome']}")
        safe_slot = html.escape(payload["data_ora"])
        email_status = (
            "Conferma inviata via email."
            if email_sent
            else "Prenotazione salvata. Configura SMTP per inviare la conferma."
        )
        cancel_link = f"/annulla?token={token}"
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
              <p>La tua richiesta e stata registrata per <strong>{safe_slot}</strong>.</p>
              <p><strong>{html.escape(email_status)}</strong></p>
              <p>Se devi annullare: <a href="{cancel_link}">Annulla prenotazione</a></p>
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
