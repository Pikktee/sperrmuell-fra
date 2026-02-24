import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "sperrmuell.db")
ADDRESSES_JSON = os.path.join(DATA_DIR, "addresses.json")

# FES Sperrmüll-API (ohne Login)
FES_API_URL = (
    "https://www.fes-frankfurt.de/services/sperrmuell"
    "?cid=33598"
    "&tx_fesbulkywaste_booking%5Baction%5D=registration"
    "&tx_fesbulkywaste_booking%5Bcontroller%5D=Booking"
    "&type=6000"
    "&cHash=bcd7a4fcebba94583574b383572fc838"
)
SCRAPE_DELAY_SECONDS = 3.0
SCRAPE_INTERVAL_HOURS = 24
# Bei "Zu viele Anfragen" (429): so lange warten vor erneutem Versuch
RETRY_AFTER_429_SECONDS = 90
MAX_RETRIES_429 = 2
