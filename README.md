# Doctor Booking

Mini gestionale prenotazioni per studio medico con sito pubblico, area admin protetta e invio email.

## Funzionalita principali
- Prenotazioni online con disponibilita aggiornate.
- Conferma email con link di annullamento.
- Dashboard admin con login, ricerca, presenza/pagamento, annulla o elimina.
- Inserimento manuale prenotazioni (es. telefoniche).
- Email di ringraziamento quando la presenza viene confermata.

## Tecnologie
- Python 3 (server HTTP + SQLite)
- HTML5, CSS3
- JavaScript (vanilla + Tailwind CDN)

## Avvio rapido
```bash
python3 server.py
```
Apri `http://127.0.0.1:8000`.

## Area admin
- Link nel footer: **Area riservata**
- Credenziali locali di default: `admin / admin`
- URL diretto: `http://127.0.0.1:8000/admin/login`

Per cambiare le credenziali:
```bash
export ADMIN_USER="tuo_utente"
export ADMIN_PASSWORD="tua_password"
```

## Email (SMTP)
Per attivare le email:
```bash
export SMTP_HOST="smtp.example.com"
export SMTP_PORT="587"    # oppure 465
export SMTP_USER="user@example.com"
export SMTP_PASS="password"
export SMTP_FROM="studio@example.com"
export SMTP_NOTIFY="segreteria@example.com"   # opzionale, invia copia
```

Tipi di email:
- Conferma prenotazione con link di annullamento.
- Ringraziamento dopo conferma presenza in admin.

## Configurazione database
Per usare un database diverso:
```bash
export BOOKING_DB="/percorso/bookings.db"
```

## Endpoint principali
- `GET /api/availability` disponibilita
- `POST /prenota` crea prenotazione
- `GET /annulla?token=...` annulla dal link email
- `GET /api/bookings` elenco prenotazioni (admin)
- `POST /api/bookings/update` presenza/pagamento (admin)
- `POST /api/bookings/cancel` annulla prenotazione (admin)
- `POST /api/bookings/delete` elimina dal database (admin)
- `POST /api/bookings/create` crea manualmente (admin)

## Note
- Le prenotazioni sono limitate ai prossimi 60 giorni.
- L'admin deve essere loggato per accedere alle API.

## Struttura progetto
- `server.py` server e logica backend
- `index.html` sito pubblico
- `admin.html` dashboard admin
- `admin-login.html` login admin
- `js/` script frontend
- `css/` stili

## Roadmap
- Notifiche push per nuove prenotazioni
- Export CSV delle prenotazioni
