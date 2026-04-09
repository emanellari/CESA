import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

APP_TITLE = "Lightweight Data Explorer"
APP_LAYOUT = "wide"

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))
HEALTHCHECK_TIMEOUT = int(os.getenv("HEALTHCHECK_TIMEOUT", 2))