"""One HTTP session for the free public APIs: they hiccup now and then, so idempotent GETs retry twice."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = 8  # seconds per attempt

session = requests.Session()
session.headers["User-Agent"] = "weather-aware-truck-routing/1.0"
session.mount("https://", HTTPAdapter(pool_maxsize=8, max_retries=Retry(
    total=2, backoff_factor=0.5, status_forcelist=[502, 503, 504], raise_on_status=False)))
