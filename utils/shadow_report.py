from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DATE_RE = re.compile(r"decisions_(\d{4}-\d{2}-\d{2})\.json$", re.IGNORECASE)


def safe_read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def load_events_any_format(p: Path) -> List[dict]:
    """
    Supports:
      - JSON array: [ {...}, {...} ]
      - JSON object: { ... }
      - NDJSON: one JSON object per line
      - empty / [] / garbage lines (ignored)
    """
    txt = safe_read_text(p).strip()
    if not txt:
        return []
    # Try JSON first
    try:
        obj = json.loads(txt)
        if isinstance(obj, list):
            return [e for e in obj if isinstance(e, dict)]
        if isinstance(obj, dict):
            return [obj]
    except Exception:
        pass

    # Fallback: NDJSON-ish
    out: List[dict] = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            if isinstance(o, dict):
                out.append(o)
        except Exception:
            # ignore junk line
            continue
    return out


def load_decisions(p: Path) -> dict:
    txt = safe_read_text(p).strip()
    if not txt:
        return {}
    return json.loads(txt)


def parse_date_from_decisions_filename(p: Path) -> Optional[str]:
    m = DATE_RE.search(p.name)
    return m.group(1) if m else None


def to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


@dataclass
class Trade:
    ticker: str
    entry_date: str
    entry_price: float
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None

    def is_open(self) -> bool:
        return self.exit_date is None

    def ret_pct(self) -> Optional[float]:
        if self.exit_price is None:
            return None
        if self.entry_price == 0:
            return None
        return (self.exit_price / self.entry_price - 1.0) * 100.0


def compute_max_drawdown(equity: List[Tuple[str, float]]) -> Tuple[float, Optional[str], Optional[str]]:
    """
    Returns (max_dd_pct_negative, peak_date, trough_date)
    """
    peak = None
    peak_date = None
    trough_date = None
    max_dd = 0.0
    max_so_far = float("-inf")

    for d, v in equity:
        if v > max_so_far:
            max_so_far = v
            peak = v
            peak_date = d
        if peak is not None and peak > 0:
            dd = v / peak - 1.0
            if dd < max_dd:
                max_dd = dd
                trough_date = d

    return max_dd * 100.0, peak_date, trough_date


def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow Mode performance report (paper equity/trades)")
    parser.add_argument("--root", default=None, help="Project root (default: auto-detect from this file)")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD (optional)")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (optional)")
    parser.add_argument("--outdir", default=None, help="Output dir (default: <root>/Output/analysis)")
    args = parser.parse_args()

    # Root autodetect: utils/shadow_report.py -> root = parents[1]
    this_file = Path(__file__).resolve()
    root = Path(args.root).resolve() if args.root else this_file.parents[1]

    decisions_dir = root / "Output" / "shadow"
    events_dir = root / "Output" / "webhooks"
    portfolio_path = root / "config" / "portfolio.json"
    outdir = Path(args.outdir).resolve() if args.outdir else (root / "Output" / "analysis")
    outdir.mkdir(parents=True, exist_ok=True)

    # Load portfolio weights (best-effort)
    weights: Dict[str, float] = {}
    if portfolio_path.exists():
        try:
            pj = json.loads(safe_read_text(portfolio_path))
            # Common shapes:
            # { "weights": { "BTCUSDT": 0.4, ... }, ...}
            # or sometimes nested etc.
            if isinstance(pj, dict) and isinstance(pj.get("weights"), dict):
                for k, v in pj["weights"].items():
                    fv = to_float(v)
                    if fv is not None:
                        weights[str(k)] = fv
        except Exception:
            pass

    # Discover decision files
    files = sorted(decisions_dir.glob("decisions_*.json"))
    dated: List[Tuple[str, Path]] = []
    for p in files:
        d = parse_date_from_decisions_filename(p)
        if d:
            dated.append((d, p))
    dated.sort(key=lambda x: x[0])

    # Apply start/end filters
    def in_range(d: str) -> bool:
        if args.start and d < args.start:
            return False
        if args.end and d > args.end:
            return False
        return True

    dated = [(d, p) for d, p in dated if in_range(d)]

    if not dated:
        print(f"[ERROR] No decisions files found in: {decisions_dir}")
        return 1

    # If no weights found, infer from first decisions file weights field or equal weights
    tickers_set = set()
    first_dec = load_decisions(dated[0][1])
    first_decisions = first_dec.get("decisions", {}) if isinstance(first_dec, dict) else {}
    if isinstance(first_decisions, dict):
        tickers_set |= set(first_decisions.keys())

    if not weights:
        # infer weights from decisions weight if present
        inferred = {}
        if isinstance(first_decisions, dict):
            for t, obj in first_decisions.items():
                if isinstance(obj, dict):
                    w = to_float(obj.get("weight"))
                    if w is not None:
                        inferred[t] = w
        if inferred:
            weights = inferred
        else:
            # equal weights
            ts = sorted(tickers_set) if tickers_set else ["BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT"]
            w = 1.0 / len(ts)
            weights = {t: w for t in ts}

    tickers = sorted(weights.keys())

    # State
    pos: Dict[str, str] = {t: "OFF" for t in tickers}           # ON/OFF
    entry_price: Dict[str, Optional[float]] = {t: None for t in tickers}
    open_trades: Dict[str, Optional[Trade]] = {t: None for t in tickers}
    trades: List[Trade] = []

    positions_rows: List[Dict[str, Any]] = []
    equity_rows: List[Dict[str, Any]] = []

    equity_series: List[Tuple[str, float]] = []

    for d, p_dec in dated:
        dec = load_decisions(p_dec)
        decisions_obj = dec.get("decisions", {}) if isinstance(dec, dict) else {}
        ms_obj = dec.get("market_structure", {}) if isinstance(dec, dict) else {}

        # Load prices from events daily_snapshot if available, else from market_structure
        p_events = events_dir / f"events_{d}.json"
        prices: Dict[str, Optional[float]] = {}
        if p_events.exists():
            evs = load_events_any_format(p_events)
            # daily_snapshot contains close price
            for e in evs:
                try:
                    if e.get("event_type") == "daily_snapshot":
                        t = str(e.get("ticker"))
                        if t in tickers:
                            prices[t] = to_float(e.get("price"))
                except Exception:
                    continue

        # fill missing from market_structure.price
        for t in tickers:
            if t not in prices or prices[t] is None:
                ms_t = ms_obj.get(t) if isinstance(ms_obj, dict) else None
                if isinstance(ms_t, dict):
                    prices[t] = to_float(ms_t.get("price"))
                else:
                    prices[t] = None

        # Detect decisions (actions/positions)
        # We'll trust decisions file for position & entry_price when BUY/SELL.
        for t in tickers:
            dobj = decisions_obj.get(t) if isinstance(decisions_obj, dict) else None
            action = None
            new_pos = None
            dec_entry = None

            if isinstance(dobj, dict):
                action = dobj.get("action")
                new_pos = dobj.get("position")
                dec_entry = to_float(dobj.get("entry_price"))

            # Normalize
            action = str(action).upper() if action is not None else "HOLD"
            new_pos = str(new_pos).upper() if new_pos is not None else pos[t]

            # Update state & trades
            prev_pos = pos[t]
            if prev_pos == "OFF" and new_pos == "ON":
                # OPEN trade
                ep = dec_entry if dec_entry is not None else prices.get(t)
                if ep is not None:
                    entry_price[t] = ep
                    tr = Trade(ticker=t, entry_date=d, entry_price=ep)
                    open_trades[t] = tr
                    trades.append(tr)
                else:
                    # can't price entry; keep None, still mark ON
                    entry_price[t] = None
                    open_trades[t] = None
                pos[t] = "ON"

            elif prev_pos == "ON" and new_pos == "OFF":
                # CLOSE trade (if we have one)
                xp = prices.get(t)
                if open_trades[t] is not None and xp is not None:
                    open_trades[t].exit_date = d
                    open_trades[t].exit_price = xp
                pos[t] = "OFF"
                entry_price[t] = None
                open_trades[t] = None
            else:
                # unchanged; ensure we have entry_price if ON but missing and we have a price (first valid mark)
                if pos[t] == "ON" and entry_price[t] is None and prices.get(t) is not None:
                    entry_price[t] = prices[t]
                    # also fix the open trade if exists without entry
                    if open_trades[t] is not None and open_trades[t].entry_price is None:
                        open_trades[t].entry_price = prices[t]  # type: ignore

        # Compute equity (cash when OFF, mtm when ON)
        row_equity: Dict[str, Any] = {"date": d}
        total = 0.0

        for t in tickers:
            w = float(weights.get(t, 0.0))
            pr = prices.get(t)
            ep = entry_price.get(t)
            position = pos[t]
            action = "HOLD"
            dobj = decisions_obj.get(t) if isinstance(decisions_obj, dict) else None
            if isinstance(dobj, dict) and dobj.get("action") is not None:
                action = str(dobj.get("action")).upper()

            if position == "ON":
                if pr is not None and ep is not None and ep != 0:
                    ratio = pr / ep
                else:
                    ratio = 1.0  # can't compute; neutral
            else:
                ratio = 1.0

            contrib = w * ratio
            total += contrib

            positions_rows.append({
                "date": d,
                "ticker": t,
                "weight": w,
                "position": position,
                "action": action,
                "price": pr,
                "entry_price": ep,
                "value_ratio": ratio,
                "contrib": contrib,
                "missing_price": pr is None,
                "missing_entry": (position == "ON" and ep is None),
                "events_file": str(p_events) if p_events.exists() else "",
                "decisions_file": str(p_dec),
            })

            row_equity[f"{t}_ratio"] = ratio
            row_equity[f"{t}_contrib"] = contrib

        row_equity["equity_total"] = total
        equity_rows.append(row_equity)
        equity_series.append((d, total))

    # Trades table (closed only metrics + open flagged)
    trades_rows: List[Dict[str, Any]] = []
    wins = 0
    closed = 0
    for tr in trades:
        is_open = tr.is_open()
        ret = tr.ret_pct()
        if (not is_open) and (ret is not None):
            closed += 1
            if ret > 0:
                wins += 1

        days_held = None
        if tr.exit_date:
            try:
                d0 = datetime.strptime(tr.entry_date, "%Y-%m-%d")
                d1 = datetime.strptime(tr.exit_date, "%Y-%m-%d")
                days_held = (d1 - d0).days
            except Exception:
                days_held = None

        trades_rows.append({
            "ticker": tr.ticker,
            "entry_date": tr.entry_date,
            "entry_price": tr.entry_price,
            "exit_date": tr.exit_date or "",
            "exit_price": tr.exit_price if tr.exit_price is not None else "",
            "return_pct": ret if ret is not None else "",
            "days_held": days_held if days_held is not None else "",
            "open": is_open,
        })

    # Summary
    start_date = equity_series[0][0]
    end_date = equity_series[-1][0]
    start_eq = equity_series[0][1]
    end_eq = equity_series[-1][1]
    total_ret_pct = (end_eq / start_eq - 1.0) * 100.0 if start_eq else 0.0

    max_dd_pct, peak_date, trough_date = compute_max_drawdown(equity_series)

    # Exposure: % of days ON per ticker
    exposure: Dict[str, float] = {}
    total_days = len(equity_rows)
    for t in tickers:
        on_days = sum(1 for r in positions_rows if r["ticker"] == t and r["position"] == "ON")
        exposure[t] = (on_days / total_days * 100.0) if total_days else 0.0

    summary = {
        "period": {"start": start_date, "end": end_date, "days": total_days},
        "equity": {"start": start_eq, "end": end_eq, "total_return_pct": total_ret_pct},
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_window": {"peak_date": peak_date, "trough_date": trough_date},
        "trades": {
            "total_opened": len(trades_rows),
            "closed": closed,
            "win_rate_pct": (wins / closed * 100.0) if closed else 0.0,
        },
        "exposure_pct": exposure,
        "tickers": tickers,
        "weights": weights,
        "notes": [
            "Equity assumes fixed weights; when position OFF, that weight stays in cash (ratio=1).",
            "If price or entry_price missing while ON, ratio defaults to 1 for that day (neutral) and is flagged in positions CSV.",
        ],
    }

    # Write CSVs
    pos_csv = outdir / "shadow_positions.csv"
    eq_csv = outdir / "shadow_equity.csv"
    tr_csv = outdir / "shadow_trades.csv"
    summary_json = outdir / "shadow_summary.json"

    def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    write_csv(pos_csv, positions_rows)
    write_csv(eq_csv, equity_rows)
    write_csv(tr_csv, trades_rows)
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== SHADOW REPORT ===")
    print(f"Root: {root}")
    print(f"Period: {start_date} -> {end_date} ({total_days} days)")
    print(f"Return: {total_ret_pct:.2f}%   Equity: {start_eq:.4f} -> {end_eq:.4f}")
    print(f"MaxDD:  {max_dd_pct:.2f}%  (peak={peak_date}, trough={trough_date})")
    print(f"Trades: opened={len(trades_rows)} closed={closed} win_rate={(wins/closed*100.0 if closed else 0.0):.1f}%")
    print("Exposure (% days ON):")
    for t in tickers:
        print(f"  {t}: {exposure[t]:.1f}%")
    print("\nSaved:")
    print(f"  {pos_csv}")
    print(f"  {eq_csv}")
    print(f"  {tr_csv}")
    print(f"  {summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
