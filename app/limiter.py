from slowapi import Limiter

from app.lang import client_ip

# Keyed off the same trusted-IP resolution used for GeoIP/i18n (app.lang.client_ip)
# rather than slowapi's default request.client.host — with
# gunicorn's forwarded_allow_ips trusting the nginx peer, request.client.host
# is populated from the *first* (client-suppliable) X-Forwarded-For entry,
# which lets an attacker bypass rate limits by varying that header per
# request. client_ip() trusts X-Real-IP (nginx overwrites it unconditionally)
# ahead of X-Forwarded-For, so it isn't spoofable the same way.
limiter = Limiter(key_func=client_ip)
