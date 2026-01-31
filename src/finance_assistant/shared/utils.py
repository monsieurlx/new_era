import logging
import os
import sys
from typing import Any, Dict

# Example utility: logger
logger = logging.getLogger("finance_assistant")

# Example utility: safe_get
def safe_get(d: Dict, key: str, default: Any = None) -> Any:
    return d.get(key, default)

# Add more shared utilities as needed
