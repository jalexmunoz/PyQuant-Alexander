import json
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

BASE_URL = "https://pyquant-alexander.onrender.com"
OUT_DIR = Path("Output/webhooks")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]

def fetch_events(date_str: str) -> str:
    url = f"{BASE_URL}/events/{date_str}"
    req = Request(url, headers={"User-Agent": "pyquant-shadow-sync"})
    with urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8")

def extract_tickers(text: str) -> set[str]:
    s = (text or "").strip()
    if not s:
        return set()

    # JSON array?
    if s.startswith("["):
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return {e.get("ticker") for e in data if isinstance(e, dict) and e.get("ticker")}
        except Exception:
            return set()

    # NDJSON (one json object per line)?
    tickers = set()
    for line in s.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("ticker"):
                tickers.add(obj["ticker"])
        except Exception:
            # ignore malformed line
            pass
    return tickers

def main():
    target = date.today().isoformat()
    out_file = OUT_DIR / f"events_{target}.json"

    attempts = 5
    sleep_s = 12

    last_text = "[]"
    for i in range(1, attempts + 1):
        text = fetch_events(target)
        last_text = text

        found = extract_tickers(text)
        ok = all(t in found for t in ASSETS)

        print(f"[SYNC] attempt {i}/{attempts} -> found={sorted(found)} ok={ok}")
        if ok:
            break

        time.sleep(sleep_s)

    out_file.write_text(last_text, encoding="utf-8")
    print(f"[SYNC] Saved: {out_file} (bytes={out_file.stat().st_size})")

if __name__ == "__main__":
    main()
