import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .plan import build_plan
from .routing import PlanError, geocode

log = logging.getLogger(__name__)
INTERVALS_MI = {10, 25, 50}
MAX_LOAD_LB = 80_000          # US federal gross weight limit
MAX_LEAD = timedelta(days=5)  # leaves room for the trip plus the 48 h slider inside the forecast


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


@csrf_exempt  # public JSON API with no cookies or sessions
@require_POST
def plan(request):
    try:
        body = json.loads(request.body)
        origin, destination = body["origin"].strip(), body["destination"].strip()
        departure = datetime.fromisoformat(body["departure"])
        load_lb, interval_mi = int(body["load_lb"]), int(body["interval_mi"])
    except (ValueError, KeyError, TypeError, AttributeError):
        return _error("Invalid request.")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    if not origin or not destination:
        return _error("Enter an origin and a destination.")
    if departure.tzinfo is None:
        return _error("Departure must include a time zone.")
    if departure < now - timedelta(hours=1):
        return _error("Departure time is in the past.")
    if departure > now + MAX_LEAD:
        return _error("Departure must be within the next 5 days (forecast range).")
    if not 0 <= load_lb <= MAX_LOAD_LB:
        return _error(f"Load must be between 0 and {MAX_LOAD_LB:,} lb.")
    if interval_mi not in INTERVALS_MI:
        return _error("Checkpoint interval must be 10, 25 or 50 miles.")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            start, end = pool.map(geocode, [origin, destination])
        if (start["lng"], start["lat"]) == (end["lng"], end["lat"]):
            return _error("Origin and destination are the same place.")
        return JsonResponse(build_plan(start, end, max(departure, now).astimezone(timezone.utc), load_lb, interval_mi))
    except PlanError as exc:
        return _error(str(exc))
    except requests.HTTPError as exc:
        log.warning("Upstream error: %s", exc)
        if exc.response.status_code == 429:
            return _error("A map or weather service is busy. Please try again in a minute.", status=503)
        return _error("A routing or weather service returned an error. Please try again.", status=502)
    except requests.RequestException as exc:
        log.warning("Upstream unreachable: %s", exc)
        return _error("A routing or weather service did not respond. Please try again.", status=502)
