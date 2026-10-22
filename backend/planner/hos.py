"""FMCSA hours of service for one property-carrying driver, so ETAs include the required stops.

Two rules shape a single trip: a 30-minute break after 8 hours of driving, and 10 hours
off duty after 11 hours of driving. The 14-hour on-duty window is always met (11 h driving
plus the 30-minute break); weekly 60/70-hour limits are outside a single trip.
"""

import math

HOUR = 3600
DRIVE_LIMIT_S = 11 * HOUR
BREAK_AFTER_S = 8 * HOUR
BREAK_S = 30 * 60
REST_S = 10 * HOUR


def wall_clock(drive_s):
    """Seconds after departure when the truck has driven `drive_s`, counting the stops before that point."""
    if drive_s <= 0:
        return 0.0
    rests = math.ceil(drive_s / DRIVE_LIMIT_S) - 1        # every finished 11 h shift ends in a rest...
    in_shift = drive_s - rests * DRIVE_LIMIT_S
    # ...and contained one 30 min break; the current shift has one once past 8 h of driving.
    return drive_s + rests * (BREAK_S + REST_S) + (BREAK_S if in_shift > BREAK_AFTER_S else 0)


def stops(total_drive_s):
    """Every stop before arrival as (kind, drive_s, starts_at_s, length_s)."""
    out = []
    shift_start = 0
    while shift_start + BREAK_AFTER_S < total_drive_s:
        at = shift_start + BREAK_AFTER_S
        out.append(("break", at, wall_clock(at), BREAK_S))
        at = shift_start + DRIVE_LIMIT_S
        if at >= total_drive_s:
            break
        out.append(("rest", at, wall_clock(at), REST_S))
        shift_start = at
    return out
