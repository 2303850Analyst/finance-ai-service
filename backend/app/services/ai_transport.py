"""Keep TLS verification enabled, optionally using an installed local proxy CA."""
import ssl
from app.config import settings


def tls_context():
    context = ssl.create_default_context()
    if settings.ai_ca_file:
        context.load_verify_locations(cafile=settings.ai_ca_file)
    return context
