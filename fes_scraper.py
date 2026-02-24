"""
Sperrmüll-Termine von der FES-Website holen (ohne Login).
Nutzt dieselben Daten wie das Online-Formular der FES.
"""
import logging
import random
import time
from datetime import datetime

import requests

from config import (
    FES_API_URL,
    SCRAPE_DELAY_SECONDS,
    ADDRESSES_JSON,
    RETRY_AFTER_429_SECONDS,
    MAX_RETRIES_429,
)
from models import load_addresses, upsert_schedule, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.fes-frankfurt.de/services/sperrmuell",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _delay_with_jitter():
    """Pause zwischen Anfragen, leicht zufällig um Rate-Limits zu mindern."""
    base = SCRAPE_DELAY_SECONDS
    jitter = base * 0.25 * (0.5 + random.random())
    time.sleep(base + jitter)


def fetch_street_suggestions(query):
    """Ruft Straßenvorschläge von der FES ab. query: Suchbegriff (min. 2 Zeichen). Returns list of street names."""
    if not query or len(query.strip()) < 2:
        return []
    data = {
        "tx_fesbulkywaste_booking[step]": "searchStreet",
        "tx_fesbulkywaste_booking[submit]": "searchStreet",
        "tx_fesbulkywaste_booking[data][street]": query.strip(),
    }
    r = requests.post(FES_API_URL, data=data, headers=HEADERS, timeout=15)
    r.raise_for_status()
    j = r.json()
    return j.get("result") or []


def fetch_housenumbers(street):
    """Ruft Hausnummern für eine Straße von der FES ab. Returns list of strings (Hausnummern)."""
    if not street or not street.strip():
        return []
    data = {
        "tx_fesbulkywaste_booking[step]": "getHousenumbers",
        "tx_fesbulkywaste_booking[submit]": "getHousenumbers",
        "tx_fesbulkywaste_booking[data][street]": street.strip(),
    }
    r = requests.post(FES_API_URL, data=data, headers=HEADERS, timeout=15)
    r.raise_for_status()
    j = r.json()
    return j.get("result") or []


def fetch_available_dates(street, housenumber):
    """
    Ruft die verfügbaren Sperrmüll-Termine für eine Adresse ab.
    Returns (weekday 0-6, fixed_date, zip_code) or None.
    Bei 429: raises requests.HTTPError mit status_code 429.
    Unterstützt auch Siedlungsabfuhr: wenn nur fixedDate gesetzt ist (keine availableDates),
    wird der Wochentag aus fixedDate abgeleitet.
    """
    data = {
        "tx_fesbulkywaste_booking[step]": "getAvailableDates",
        "tx_fesbulkywaste_booking[submit]": "getAvailableDates",
        "tx_fesbulkywaste_booking[data][street]": street,
        "tx_fesbulkywaste_booking[data][housenumber]": str(housenumber),
    }
    r = requests.post(FES_API_URL, data=data, headers=HEADERS, timeout=20)
    r.raise_for_status()
    j = r.json()

    zip_code = j.get("zip") or None
    fixed_date = j.get("fixedDate")
    if fixed_date and isinstance(fixed_date, str):
        try:
            datetime.fromisoformat(fixed_date.replace("Z", "+00:00"))
        except Exception:
            fixed_date = None
    elif fixed_date is False:
        fixed_date = None

    dates = j.get("availableDates") or []
    if dates:
        first = dates[0]
        if isinstance(first, str):
            dt = datetime.fromisoformat(first.replace("Z", "+00:00"))
            weekday = dt.weekday()
        else:
            weekday = 0
        return (weekday, fixed_date, zip_code)

    # Siedlungsabfuhr: nur fixedDate, keine verfügbaren Einzeltermine
    if fixed_date:
        try:
            dt = datetime.fromisoformat(fixed_date.replace("Z", "+00:00"))
            weekday = dt.weekday()
            return (weekday, fixed_date, zip_code)
        except Exception:
            pass

    return None


def scrape_all():
    init_db()
    addresses = load_addresses()
    if not addresses:
        logger.warning("Keine Adressen in %s", ADDRESSES_JSON)
        return

    ok = 0
    fail_no_dates = 0
    fail_429 = 0
    fail_other = 0
    failed_stadtteile = []

    for i, row in enumerate(addresses):
        stadtteil = row.get("stadtteil", "")
        street = row.get("street", "")
        number = row.get("number", "")
        if not stadtteil or not street or not number:
            fail_other += 1
            continue

        retries_429 = 0
        result = None

        while retries_429 <= MAX_RETRIES_429:
            try:
                result = fetch_available_dates(street, number)
                break
            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    retries_429 += 1
                    if retries_429 <= MAX_RETRIES_429:
                        wait = RETRY_AFTER_429_SECONDS
                        logger.warning(
                            "Zu viele Anfragen (429) für %s %s – warte %d s (Versuch %d/%d)",
                            street, number, wait, retries_429, MAX_RETRIES_429 + 1,
                        )
                        time.sleep(wait)
                    else:
                        fail_429 += 1
                        failed_stadtteile.append((stadtteil, "429 Zu viele Anfragen"))
                        logger.info("[%d/%d] %s %s %s -> übersprungen (429)", i + 1, len(addresses), stadtteil, street, number)
                        break
                else:
                    fail_other += 1
                    failed_stadtteile.append((stadtteil, str(e.response.status_code)))
                    logger.info("[%d/%d] %s %s %s -> Fehler %s", i + 1, len(addresses), stadtteil, street, number, e.response.status_code)
                    break
            except Exception as e:
                fail_other += 1
                failed_stadtteile.append((stadtteil, str(e)[:50]))
                logger.warning("Anfrage fehlgeschlagen für %s %s: %s", street, number, e)
                break

        if result is None and retries_429 <= MAX_RETRIES_429:
            fail_no_dates += 1
            failed_stadtteile.append((stadtteil, "Keine Termine"))
            logger.info("[%d/%d] %s %s %s -> keine Termine", i + 1, len(addresses), stadtteil, street, number)
        elif result is not None:
            weekday, fixed_date, zip_code = result
            upsert_schedule(stadtteil, street, number, weekday, fixed_date, zip_code)
            ok += 1
            wd_name = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][weekday]
            suffix = " (Siedlungsabfuhr)" if fixed_date else ""
            logger.info("[%d/%d] %s %s %s -> %s%s", i + 1, len(addresses), stadtteil, street, number, wd_name, suffix)

        _delay_with_jitter()

    logger.info(
        "Scrape abgeschlossen: %d erfolgreich, %d ohne Termine, %d Rate-Limit (429), %d sonstige Fehler",
        ok, fail_no_dates, fail_429, fail_other,
    )
    if failed_stadtteile:
        logger.info("Übersprungene Stadtteile (Auswahl): %s", failed_stadtteile[:15])
