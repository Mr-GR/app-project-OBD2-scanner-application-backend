# api/utils/dtc.py
from functools import lru_cache
from pathlib import Path
import json, os, requests

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_CODES = BASE_DIR / "resources" / "dtc_codes.json"

@lru_cache
def _local_table():
    with LOCAL_CODES.open() as fp:
        return json.load(fp)

def get_code_description(code: str) -> str:
    code = code.strip().upper()
    return _local_table().get(code) or "Unknown code"
