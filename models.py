import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from config import DB_PATH, ADDRESSES_JSON

FRANKFURTER_STADTTEILE = [
    "Altstadt", "Bahnhofsviertel", "Bergen-Enkheim", "Berkersheim",
    "Bockenheim", "Bonames", "Bornheim", "Dornbusch", "Eckenheim",
    "Eschersheim", "Fechenheim", "Frankfurter Berg", "Gallus",
    "Ginnheim", "Griesheim", "Gutleutviertel", "Harheim", "Hausen",
    "Heddernheim", "Höchst", "Innenstadt", "Kalbach-Riedberg",
    "Nied", "Nieder-Erlenbach", "Nieder-Eschbach", "Niederrad",
    "Niederursel", "Nordend-Ost", "Nordend-West", "Nordweststadt",
    "Oberrad", "Ostend", "Praunheim", "Preungesheim", "Riederwald",
    "Rödelheim", "Sachsenhausen-Nord", "Sachsenhausen-Süd",
    "Schwanheim", "Seckbach", "Sindlingen", "Sossenheim",
    "Unterliederbach", "Westend-Nord", "Westend-Süd", "Zeilsheim",
]

WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sperrmuell_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stadtteil TEXT NOT NULL,
            street TEXT NOT NULL,
            housenumber TEXT NOT NULL,
            weekday INTEGER NOT NULL,
            fixed_date TEXT,
            zip_code TEXT,
            scraped_at TEXT NOT NULL,
            UNIQUE(stadtteil, street, housenumber)
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_stadtteil ON sperrmuell_schedule(stadtteil);
        CREATE INDEX IF NOT EXISTS idx_schedule_weekday ON sperrmuell_schedule(weekday);
    """)
    conn.commit()
    conn.close()


def load_addresses():
    path = Path(ADDRESSES_JSON)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def upsert_schedule(stadtteil, street, housenumber, weekday, fixed_date=None, zip_code=None):
    conn = get_db()
    conn.execute(
        """INSERT INTO sperrmuell_schedule
           (stadtteil, street, housenumber, weekday, fixed_date, zip_code, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(stadtteil, street, housenumber) DO UPDATE SET
             weekday = excluded.weekday,
             fixed_date = excluded.fixed_date,
             zip_code = excluded.zip_code,
             scraped_at = excluded.scraped_at""",
        (stadtteil, street, housenumber, weekday, fixed_date, zip_code, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_schedule_by_stadtteil(stadtteil=None):
    conn = get_db()
    if stadtteil:
        rows = conn.execute(
            """SELECT * FROM sperrmuell_schedule
               WHERE stadtteil = ?
               ORDER BY weekday, street""",
            (stadtteil,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM sperrmuell_schedule
               ORDER BY stadtteil, weekday, street"""
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_siedlungsabfuhr_entries(stadtteil=None):
    """Einträge mit Siedlungsabfuhr (fester Platz, alle 4 Wochen)."""
    conn = get_db()
    if stadtteil:
        rows = conn.execute(
            """SELECT * FROM sperrmuell_schedule
               WHERE fixed_date IS NOT NULL AND fixed_date != ''
               AND stadtteil = ?
               ORDER BY stadtteil, street""",
            (stadtteil,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM sperrmuell_schedule
               WHERE fixed_date IS NOT NULL AND fixed_date != ''
               ORDER BY stadtteil, street"""
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def next_dates_for_fixed_date(fixed_date_iso, count=6):
    """Nächste Termine bei Siedlungsabfuhr (alle 4 Wochen ab fixed_date)."""
    if not fixed_date_iso:
        return []
    try:
        d = date.fromisoformat(fixed_date_iso[:10])
    except Exception:
        return []
    today = date.today()
    result = []
    # Nächsten Termin >= heute finden (kann fixed_date selbst sein)
    while d < today:
        d += timedelta(days=28)
    for _ in range(count):
        result.append(d.isoformat())
        d += timedelta(days=28)
    return result


def get_schedule_grouped_by_weekday():
    rows = get_schedule_by_stadtteil()
    by_weekday = {}
    for r in rows:
        wd = r["weekday"]
        if wd not in by_weekday:
            by_weekday[wd] = []
        by_weekday[wd].append(r)
    return by_weekday


def get_stadtteile_with_schedule():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT stadtteil FROM sperrmuell_schedule ORDER BY stadtteil"
    ).fetchall()
    conn.close()
    return [r["stadtteil"] for r in rows]


def next_dates_for_weekday(weekday, count=8):
    """Nächste count Termine für einen Wochentag (0=Mo, 6=So)."""
    today = date.today()
    # Nächster Wochentag (kann heute sein)
    days_ahead = (weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # Nächste Woche
    result = []
    for _ in range(count):
        d = today + timedelta(days=days_ahead)
        result.append(d.isoformat())
        days_ahead += 7
    return result


def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM sperrmuell_schedule").fetchone()[0]
    stadtteile = conn.execute("SELECT COUNT(DISTINCT stadtteil) FROM sperrmuell_schedule").fetchone()[0]
    conn.close()
    by_weekday = get_schedule_grouped_by_weekday()
    return {
        "total_entries": total,
        "stadtteile": stadtteile,
        "by_weekday": {k: len(v) for k, v in by_weekday.items()},
    }
