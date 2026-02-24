import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "sperrmuell.db")
ADDRESSES_JSON = os.path.join(DATA_DIR, "addresses.json")

# Beim ersten Start mit Volume: Standard-Adressen aus dem Image nach /data kopieren
if os.environ.get("DATA_DIR"):
    _default_addresses = os.path.join(BASE_DIR, "data", "addresses.json")
    if os.path.isfile(_default_addresses) and not os.path.isfile(ADDRESSES_JSON):
        import shutil
        shutil.copy2(_default_addresses, ADDRESSES_JSON)

# FES Sperrmüll-API (ohne Login)
FES_API_URL = (
    "https://www.fes-frankfurt.de/services/sperrmuell"
    "?cid=33598"
    "&tx_fesbulkywaste_booking%5Baction%5D=registration"
    "&tx_fesbulkywaste_booking%5Bcontroller%5D=Booking"
    "&type=6000"
    "&cHash=bcd7a4fcebba94583574b383572fc838"
)
# Öffentliche Buchungsseite (gleiche URL-Basis; Adresse kann als Query angehängt werden)
FES_BOOKING_PAGE_URL = FES_API_URL
SCRAPE_DELAY_SECONDS = 3.0
SCRAPE_INTERVAL_HOURS = 24
# Bei "Zu viele Anfragen" (429): so lange warten vor erneutem Versuch
RETRY_AFTER_429_SECONDS = 90
MAX_RETRIES_429 = 2
