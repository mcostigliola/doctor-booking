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
ADMIN_COOKIE_NAME = "admin_session"
ADMIN_TOKENS: set[str] = set()


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
                created_at TEXT NOT NULL,
                attended INTEGER DEFAULT 0,
                paid INTEGER DEFAULT 0,
                thanked_at TEXT
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
        if "attended" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN attended INTEGER DEFAULT 0")
        if "paid" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN paid INTEGER DEFAULT 0")
        if "thanked_at" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN thanked_at TEXT")

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


def send_thank_you_email(payload: dict[str, str]) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "")

    if not (smtp_host and smtp_user and smtp_pass and smtp_from):
        return False

    message = EmailMessage()
    message["Subject"] = "Grazie per la visita"
    message["From"] = smtp_from
    message["To"] = payload["email"]

    message.set_content(
        "\n".join(
            [
                "Grazie per aver visitato il nostro studio.",
                "",
                f"Nome: {payload['nome']} {payload['cognome']}",
                f"Data e ora: {payload['data_ora']}",
                "",
                "Restiamo a disposizione per qualsiasi necessita.",
                "A presto.",
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


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _extract_admin_token(cookie_header: str | None) -> str:
    if not cookie_header:
        return ""
    parts = [item.strip() for item in cookie_header.split(";") if "=" in item]
    for part in parts:
        name, value = part.split("=", 1)
        if name.strip() == ADMIN_COOKIE_NAME:
            return value.strip()
    return ""


def fetch_bookings() -> list[dict[str, object]]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, nome, cognome, telefono, email, data_ora, data, ora, note, status,
                   created_at, attended, paid, thanked_at, canceled_at
            FROM bookings
            ORDER BY
              CASE WHEN data IS NULL THEN 1 ELSE 0 END,
              data ASC,
              CASE WHEN ora IS NULL THEN 1 ELSE 0 END,
              ora ASC,
              created_at ASC
            """
        ).fetchall()

    bookings = []
    for row in rows:
        (
            booking_id,
            nome,
            cognome,
            telefono,
            email,
            data_ora,
            data,
            ora,
            note,
            status,
            created_at,
            attended,
            paid,
            thanked_at,
            canceled_at,
        ) = row
        bookings.append(
            {
                "id": booking_id,
                "nome": nome,
                "cognome": cognome,
                "telefono": telefono,
                "email": email,
                "data_ora": data_ora,
                "data": data,
                "ora": ora,
                "note": note or "",
                "status": status,
                "created_at": created_at,
                "attended": bool(attended),
                "paid": bool(paid),
                "thanked_at": thanked_at,
                "canceled_at": canceled_at,
            }
        )

    return bookings


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

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode("utf-8")

    def _parse_body(self) -> dict[str, str]:
        raw = self._read_body()
        if "application/json" in (self.headers.get("Content-Type") or ""):
            try:
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                return {}
            return {k: str(v) for k, v in data.items() if v is not None}
        return {k: v[0] for k, v in parse_qs(raw).items()}

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

        if requested == "/api/bookings":
            token = _extract_admin_token(self.headers.get("Cookie"))
            if token not in ADMIN_TOKENS:
                self.send_error(HTTPStatus.UNAUTHORIZED, "Non autorizzato")
                return
            payload = fetch_bookings()
            body = json.dumps({"bookings": payload}).encode("utf-8")
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

        if requested == "/admin.html" or requested == "/admin":
            token = _extract_admin_token(self.headers.get("Cookie"))
            if token not in ADMIN_TOKENS:
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", "/admin/login")
                self.end_headers()
                return
            self._send_file(BASE_DIR / "admin.html")
            return

        if requested == "/admin/login":
            self._send_file(BASE_DIR / "admin-login.html")
            return

        if requested == "/admin/logout":
            token = _extract_admin_token(self.headers.get("Cookie"))
            if token:
                ADMIN_TOKENS.discard(token)
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/admin/login")
            self.send_header(
                "Set-Cookie",
                f"{ADMIN_COOKIE_NAME}=; HttpOnly; Path=/; SameSite=Strict; Max-Age=0",
            )
            self.end_headers()
            return

        if requested.startswith("/css/") or requested.startswith("/js/"):
            self._send_file(BASE_DIR / requested.lstrip("/"))
            return

        if requested.startswith("/public/"):
            self._send_file(BASE_DIR / requested.lstrip("/"))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path == "/admin/login":
            data = self._parse_body()
            username = data.get("username", "").strip()
            password = data.get("password", "").strip()
            admin_user = os.getenv("ADMIN_USER", "admin")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin")
            if username != admin_user or password != admin_password:
                self._send_text("<h1>Credenziali non valide</h1><p>Riprova.</p>", status=401)
                return

            token = secrets.token_urlsafe(24)
            ADMIN_TOKENS.add(token)

            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/admin.html")
            self.send_header("Set-Cookie", f"{ADMIN_COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=Strict")
            self.end_headers()
            return

        if self.path == "/api/bookings/create":
            token = _extract_admin_token(self.headers.get("Cookie"))
            if token not in ADMIN_TOKENS:
                self.send_error(HTTPStatus.UNAUTHORIZED, "Non autorizzato")
                return

            data = self._parse_body()
            required_fields = ["nome", "cognome", "telefono", "email", "data", "ora"]
            missing = [field for field in required_fields if not data.get(field)]
            if missing:
                self.send_error(HTTPStatus.BAD_REQUEST, "Dati mancanti")
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
                self.send_error(HTTPStatus.BAD_REQUEST, "Data non valida")
                return

            if parsed_date < min_date or parsed_date > max_date:
                self.send_error(HTTPStatus.BAD_REQUEST, "Data fuori intervallo")
                return

            if booking_time not in TIME_SLOTS:
                self.send_error(HTTPStatus.BAD_REQUEST, "Orario non valido")
                return

            payload = {
                "nome": data["nome"].strip(),
                "cognome": data["cognome"].strip(),
                "telefono": data["telefono"].strip(),
                "email": data["email"].strip(),
                "note": data.get("note", "").strip(),
            }

            token_value = secrets.token_urlsafe(24)

            with sqlite3.connect(DB_PATH) as conn:
                exists = conn.execute(
                    """
                    SELECT 1 FROM bookings
                    WHERE data = ? AND ora = ? AND status = 'booked'
                    """,
                    (booking_date, booking_time),
                ).fetchone()
                if exists:
                    self.send_error(HTTPStatus.CONFLICT, "Slot non disponibile")
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
                        data_ora,
                        booking_date,
                        booking_time,
                        payload["note"],
                        token_value,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

                new_booking = conn.execute(
                    """
                    SELECT id, nome, cognome, telefono, email, data_ora, data, ora, note, status,
                           created_at, attended, paid, thanked_at, canceled_at
                    FROM bookings
                    WHERE rowid = last_insert_rowid()
                    """
                ).fetchone()

            (
                booking_id_value,
                nome,
                cognome,
                telefono,
                email,
                data_ora,
                data_value,
                ora,
                note,
                status,
                created_at,
                attended_value,
                paid_value,
                thanked_at,
                canceled_at,
            ) = new_booking

            response_payload = {
                "booking": {
                    "id": booking_id_value,
                    "nome": nome,
                    "cognome": cognome,
                    "telefono": telefono,
                    "email": email,
                    "data_ora": data_ora,
                    "data": data_value,
                    "ora": ora,
                    "note": note or "",
                    "status": status,
                    "created_at": created_at,
                    "attended": bool(attended_value),
                    "paid": bool(paid_value),
                    "thanked_at": thanked_at,
                    "canceled_at": canceled_at,
                }
            }

            body = json.dumps(response_payload).encode("utf-8")
            self.send_response(HTTPStatus.CREATED)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/bookings/cancel":
            token = _extract_admin_token(self.headers.get("Cookie"))
            if token not in ADMIN_TOKENS:
                self.send_error(HTTPStatus.UNAUTHORIZED, "Non autorizzato")
                return

            data = self._parse_body()
            booking_id = data.get("id", "").strip()
            if not booking_id.isdigit():
                self.send_error(HTTPStatus.BAD_REQUEST, "Id non valido")
                return

            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    """
                    SELECT id, status
                    FROM bookings
                    WHERE id = ?
                    """,
                    (int(booking_id),),
                ).fetchone()

                if not row:
                    self.send_error(HTTPStatus.NOT_FOUND, "Prenotazione non trovata")
                    return

                if row[1] != "canceled":
                    conn.execute(
                        "UPDATE bookings SET status = 'canceled', canceled_at = ? WHERE id = ?",
                        (datetime.now(timezone.utc).isoformat(), int(booking_id)),
                    )

                updated = conn.execute(
                    """
                    SELECT id, nome, cognome, telefono, email, data_ora, data, ora, note, status,
                           created_at, attended, paid, thanked_at, canceled_at
                    FROM bookings
                    WHERE id = ?
                    """,
                    (int(booking_id),),
                ).fetchone()

            (
                booking_id_value,
                nome,
                cognome,
                telefono,
                email,
                data_ora,
                data_value,
                ora,
                note,
                status,
                created_at,
                attended_value,
                paid_value,
                thanked_at,
                canceled_at,
            ) = updated

            response_payload = {
                "booking": {
                    "id": booking_id_value,
                    "nome": nome,
                    "cognome": cognome,
                    "telefono": telefono,
                    "email": email,
                    "data_ora": data_ora,
                    "data": data_value,
                    "ora": ora,
                    "note": note or "",
                    "status": status,
                    "created_at": created_at,
                    "attended": bool(attended_value),
                    "paid": bool(paid_value),
                    "thanked_at": thanked_at,
                    "canceled_at": canceled_at,
                }
            }
            body = json.dumps(response_payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/bookings/delete":
            token = _extract_admin_token(self.headers.get("Cookie"))
            if token not in ADMIN_TOKENS:
                self.send_error(HTTPStatus.UNAUTHORIZED, "Non autorizzato")
                return

            data = self._parse_body()
            booking_id = data.get("id", "").strip()
            if not booking_id.isdigit():
                self.send_error(HTTPStatus.BAD_REQUEST, "Id non valido")
                return

            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT id FROM bookings WHERE id = ?",
                    (int(booking_id),),
                ).fetchone()

                if not row:
                    self.send_error(HTTPStatus.NOT_FOUND, "Prenotazione non trovata")
                    return

                conn.execute("DELETE FROM bookings WHERE id = ?", (int(booking_id),))

            response_payload = {"deleted": True, "id": int(booking_id)}
            body = json.dumps(response_payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/bookings/update":
            token = _extract_admin_token(self.headers.get("Cookie"))
            if token not in ADMIN_TOKENS:
                self.send_error(HTTPStatus.UNAUTHORIZED, "Non autorizzato")
                return
            data = self._parse_body()
            booking_id = data.get("id", "").strip()
            if not booking_id.isdigit():
                self.send_error(HTTPStatus.BAD_REQUEST, "Id non valido")
                return

            attended = _parse_bool(data.get("attended"))
            paid = _parse_bool(data.get("paid"))

            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    """
                    SELECT id, nome, cognome, email, data_ora, attended, paid, thanked_at
                    FROM bookings
                    WHERE id = ?
                    """,
                    (int(booking_id),),
                ).fetchone()

                if not row:
                    self.send_error(HTTPStatus.NOT_FOUND, "Prenotazione non trovata")
                    return

                (
                    booking_id_value,
                    nome,
                    cognome,
                    email,
                    data_ora,
                    attended_current,
                    paid_current,
                    thanked_at,
                ) = row

                new_attended = attended_current if attended is None else int(attended)
                new_paid = paid_current if paid is None else int(paid)

                updates = []
                params: list[object] = []
                if new_attended != attended_current:
                    updates.append("attended = ?")
                    params.append(new_attended)
                if new_paid != paid_current:
                    updates.append("paid = ?")
                    params.append(new_paid)

                thank_you_sent = False
                if updates:
                    params.append(booking_id_value)
                    conn.execute(
                        f"UPDATE bookings SET {', '.join(updates)} WHERE id = ?",
                        params,
                    )

                if new_attended == 1 and not attended_current and not thanked_at:
                    payload = {
                        "nome": nome,
                        "cognome": cognome,
                        "email": email,
                        "data_ora": data_ora or "",
                    }
                    try:
                        thank_you_sent = send_thank_you_email(payload)
                    except Exception:
                        thank_you_sent = False
                    if thank_you_sent:
                        thanked_at = datetime.now(timezone.utc).isoformat()
                        conn.execute(
                            "UPDATE bookings SET thanked_at = ? WHERE id = ?",
                            (thanked_at, booking_id_value),
                        )

                updated = conn.execute(
                    """
                    SELECT id, nome, cognome, telefono, email, data_ora, data, ora, note, status,
                           created_at, attended, paid, thanked_at, canceled_at
                    FROM bookings
                    WHERE id = ?
                    """,
                    (booking_id_value,),
                ).fetchone()

            (
                booking_id_value,
                nome,
                cognome,
                telefono,
                email,
                data_ora,
                data_value,
                ora,
                note,
                status,
                created_at,
                attended_value,
                paid_value,
                thanked_at,
                canceled_at,
            ) = updated

            response_payload = {
                "booking": {
                    "id": booking_id_value,
                    "nome": nome,
                    "cognome": cognome,
                    "telefono": telefono,
                    "email": email,
                    "data_ora": data_ora,
                    "data": data_value,
                    "ora": ora,
                    "note": note or "",
                    "status": status,
                    "created_at": created_at,
                    "attended": bool(attended_value),
                    "paid": bool(paid_value),
                    "thanked_at": thanked_at,
                    "canceled_at": canceled_at,
                },
                "thank_you_email": {"sent": thank_you_sent},
            }

            body = json.dumps(response_payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path != "/prenota":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        data = self._parse_body()

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
