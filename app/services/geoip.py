"""
Looks up a visitor's country from their IP using a local MaxMind
GeoLite2-Country database (see README for how to obtain one — this is a
free download that requires a MaxMind account). Used only to pick a
sensible *default* UI language for first-time visitors; never required for
the site to function.
"""
import logging
from pathlib import Path
from typing import Optional

import geoip2.database
import geoip2.errors

from app.config import settings

logger = logging.getLogger("geoip")

_reader: Optional["geoip2.database.Reader"] = None
_load_attempted = False


def _get_reader() -> Optional["geoip2.database.Reader"]:
    global _reader, _load_attempted
    if _load_attempted:
        return _reader
    _load_attempted = True
    path = Path(settings.GEOIP_DB_PATH)
    if not path.is_file():
        logger.warning(
            "GeoIP database not found at %s — new visitors will default to "
            "DEFAULT_LANGUAGE (%s) until it's added. See README.",
            path,
            settings.DEFAULT_LANGUAGE,
        )
        return None
    try:
        _reader = geoip2.database.Reader(str(path))
    except Exception:
        logger.exception("Failed to open GeoIP database at %s", path)
        _reader = None
    return _reader


def country_for_ip(ip: str) -> Optional[str]:
    reader = _get_reader()
    if reader is None or not ip:
        return None
    try:
        return reader.country(ip).country.iso_code
    except (geoip2.errors.AddressNotFoundError, ValueError):
        return None
    except Exception:
        logger.exception("GeoIP lookup failed for %s", ip)
        return None
