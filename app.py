import logging
import os
import threading
from datetime import date

from flask import Flask, render_template, request, jsonify, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
import requests

from models import (
    init_db,
    get_schedule_by_stadtteil,
    get_schedule_grouped_by_weekday,
    get_stadtteile_with_schedule,
    get_siedlungsabfuhr_entries,
    next_dates_for_weekday,
    next_dates_for_fixed_date,
    FRANKFURTER_STADTTEILE,
    WEEKDAY_NAMES,
)
from fes_scraper import scrape_all, fetch_available_dates, fetch_street_suggestions, fetch_housenumbers
from config import SCRAPE_INTERVAL_HOURS, FES_BOOKING_PAGE_URL

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DB und Scheduler auch unter Gunicorn starten (nicht nur bei python app.py)
init_db()
threading.Thread(target=scrape_all, daemon=True).start()
_scheduler = BackgroundScheduler()
_scheduler.add_job(scrape_all, "interval", hours=SCRAPE_INTERVAL_HOURS)
_scheduler.start()


@app.template_filter("weekday_name")
def weekday_name_filter(weekday_int):
    return WEEKDAY_NAMES[weekday_int] if 0 <= weekday_int <= 6 else "?"


@app.template_filter("short_date")
def short_date_filter(date_str):
    d = date.fromisoformat(date_str)
    return f"{d.day}.{d.month:02d}.{d.year}"


@app.context_processor
def inject_globals():
    return {
        "today": date.today().isoformat(),
        "all_stadtteile": FRANKFURTER_STADTTEILE,
        "weekday_names": WEEKDAY_NAMES,
        "fes_booking_page_url": FES_BOOKING_PAGE_URL,
    }


@app.route("/")
def index():
    street = (request.args.get("street") or "").strip()
    housenumber = (request.args.get("housenumber") or "").strip()
    lookup_result = None

    if street and housenumber:
        try:
            result = fetch_available_dates(street, housenumber)
            if result is not None:
                weekday, fixed_date, zip_code = result
                weekday_name = WEEKDAY_NAMES[weekday]
                if fixed_date:
                    next_dates = next_dates_for_fixed_date(fixed_date, 8)
                else:
                    next_dates = next_dates_for_weekday(weekday, 8)
                lookup_result = {
                    "success": True,
                    "street": street,
                    "housenumber": housenumber,
                    "weekday": weekday,
                    "weekday_name": weekday_name,
                    "fixed_date": fixed_date,
                    "is_siedlungsabfuhr": bool(fixed_date),
                    "zip_code": zip_code,
                    "next_dates": next_dates,
                }
            else:
                lookup_result = {
                    "success": False,
                    "street": street,
                    "housenumber": housenumber,
                    "error": "Für diese Adresse wurden keine Sperrmüll-Termine gefunden. Bitte Schreibweise prüfen (z.B. „Str.“ statt „Strasse“) oder eine andere Hausnummer versuchen.",
                }
        except requests.HTTPError as e:
            if e.response.status_code == 429:
                lookup_result = {
                    "success": False,
                    "street": street,
                    "housenumber": housenumber,
                    "error": "Die Abfrage ist derzeit zu oft genutzt. Bitte in einer Minute erneut versuchen.",
                }
            else:
                lookup_result = {
                    "success": False,
                    "street": street,
                    "housenumber": housenumber,
                    "error": "Die Abfrage konnte nicht durchgeführt werden. Bitte später erneut versuchen.",
                }
        except Exception:
            logger.exception("Adress-Suche fehlgeschlagen")
            lookup_result = {
                "success": False,
                "street": street,
                "housenumber": housenumber,
                "error": "Ein Fehler ist aufgetreten. Bitte Schreibweise der Straße prüfen (z.B. „Str.“ statt „Strasse“) und es erneut versuchen.",
            }

    by_weekday = get_schedule_grouped_by_weekday()
    stadtteile_with_data = get_stadtteile_with_schedule()
    siedlungsabfuhr = get_siedlungsabfuhr_entries()
    return render_template(
        "index.html",
        lookup_result=lookup_result,
        street=street,
        housenumber=housenumber,
        by_weekday=by_weekday,
        stadtteile_with_data=stadtteile_with_data,
        siedlungsabfuhr=siedlungsabfuhr,
        next_dates_for_weekday=next_dates_for_weekday,
        next_dates_for_fixed_date=next_dates_for_fixed_date,
    )


@app.route("/api/streets")
def api_streets():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"streets": []})
    try:
        streets = fetch_street_suggestions(q)
        return jsonify({"streets": streets})
    except Exception as e:
        logger.warning("Straßensuche fehlgeschlagen: %s", e)
        return jsonify({"streets": []}), 500


@app.route("/api/housenumbers")
def api_housenumbers():
    street = (request.args.get("street") or "").strip()
    if not street:
        return jsonify({"housenumbers": []})
    try:
        numbers = fetch_housenumbers(street)
        return jsonify({"housenumbers": numbers})
    except Exception as e:
        logger.warning("Hausnummern-Suche fehlgeschlagen: %s", e)
        return jsonify({"housenumbers": []}), 500


@app.route("/termine")
def termine():
    stadtteil = request.args.get("stadtteil")
    schedule = get_schedule_by_stadtteil(stadtteil=stadtteil)
    stadtteile_with_data = get_stadtteile_with_schedule()
    siedlungsabfuhr = get_siedlungsabfuhr_entries(stadtteil=stadtteil)
    return render_template(
        "termine.html",
        schedule=schedule,
        stadtteile_with_data=stadtteile_with_data,
        selected_stadtteil=stadtteil,
        siedlungsabfuhr=siedlungsabfuhr,
        next_dates_for_weekday=next_dates_for_weekday,
        next_dates_for_fixed_date=next_dates_for_fixed_date,
    )


@app.route("/suchen", methods=["GET", "POST"], endpoint="address_lookup")
def suchen():
    """Weiterleitung zur Startseite – Adresssuche liegt auf /."""
    if request.method == "GET" and not request.args:
        return redirect(url_for("index"))
    args = {}
    if request.args.get("street"):
        args["street"] = request.args.get("street")
    if request.args.get("housenumber"):
        args["housenumber"] = request.args.get("housenumber")
    return redirect(url_for("index", **args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port, use_reloader=False)
