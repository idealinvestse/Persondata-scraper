"""Huvudmodul som integrerar alla moduler för MerinfoScraper"""

from merinfo_scraper_modular.dataclasses_module import *
from merinfo_scraper_modular.utils_module import *
from merinfo_scraper_modular.cache_module import *
from merinfo_scraper_modular.logging_module import *
from merinfo_scraper_modular.core_module import *

# Förhindra import-krasch om network_module är ofullständig
try:
    from merinfo_scraper_modular.network_module import *  # noqa: F401,F403
except Exception as _e:
    # Logga senare när loggern är initierad
    _NETWORK_MODULE_IMPORT_ERROR = _e
else:
    _NETWORK_MODULE_IMPORT_ERROR = None

logger = setup_logging()

if '_NETWORK_MODULE_IMPORT_ERROR' in globals() and _NETWORK_MODULE_IMPORT_ERROR:
    logger.debug(f"network_module kunde inte importeras: {_NETWORK_MODULE_IMPORT_ERROR}")

# Eventuell ytterligare startkod eller exempel här

