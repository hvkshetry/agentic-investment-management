import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "portfolio"
STATE_DIR = ROOT / "Investing" / "State" / "Positions"


def parse_number(s: str) -> float:
    """Parse a number that may contain commas, dollar signs, or percentage signs."""
    if s is None:
        return 0.0
    s = str(s).strip()
    if s == "" or s.upper() == "N/A":
        return 0.0
    # Remove $ , % and quotes
    for ch in ["$", ",", "%"]:
        s = s.replace(ch, "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def classify_asset(symbol: str, name: str) -> str:
    s = (symbol or "").upper()
    n = (name or "").lower()
    if s in {"VMFXX"} or "money market" in n:
        return "Cash"
    etf_keywords = [
        "etf",
        "index",
        "trust",
    ]
    bond_keywords = ["tax exempt", "bond", "treasury", "fixed income"]
    if any(k in n for k in bond_keywords):
        return "Fixed Income"
    if any(k in n for k in etf_keywords):
        return "ETF"
    return "Equity"


def upsert_position(positions: Dict[str, Dict[str, Any]], symbol: str, shares: float, price: float, value: float, name: str):
    if not symbol:
        return
    t = symbol.upper()
    p = positions.setdefault(
        t,
        {
            "ticker": t,
            "shares": 0.0,
            "currentPrice": 0.0,
            "marketValue": 0.0,
            "assetClass": classify_asset(t, name),
            "name": name,
        },
    )
    p["shares"] += shares
    # Prefer price if provided, else infer from value/shares
    if price > 0:
        p["currentPrice"] = price
    elif shares > 0:
        p["currentPrice"] = value / shares
    p["marketValue"] += value if value > 0 else price * shares


def import_ubs(csv_path: Path, positions: Dict[str, Dict[str, Any]]):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = None
        for row in reader:
            if not row:
                continue
            # Detect header
            if row[0].strip().upper() == "ACCOUNT NUMBER":
                header = [c.strip().upper() for c in row]
                continue
            if not header:
                continue
            # Build mapping
            row_map = {header[i]: (row[i] if i < len(row) else "") for i in range(len(header))}
            symbol = row_map.get("SYMBOL", "").strip()
            if not symbol or symbol.upper() == "N/A":
                continue
            name = row_map.get("DESCRIPTION", "").strip()
            qty = parse_number(row_map.get("QUANTITY", "0"))
            price = parse_number(row_map.get("PRICE", "0"))
            value = parse_number(row_map.get("VALUE", "0"))
            if qty <= 0 and value <= 0:
                continue
            upsert_position(positions, symbol, qty, price, value, name)


def import_vanguard(csv_path: Path, positions: Dict[str, Dict[str, Any]]):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    # Find the section starting with the holdings header
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "account number" and len(row) >= 6 and row[2].strip().lower() == "symbol":
            header_idx = i
            break
    if header_idx is None:
        return
    header = [c.strip().lower() for c in rows[header_idx]]
    sym_idx = header.index("symbol")
    name_idx = header.index("investment name")
    shares_idx = header.index("shares")
    price_idx = header.index("share price")
    value_idx = header.index("total value")
    i = header_idx + 1
    while i < len(rows):
        row = rows[i]
        i += 1
        if not row or len(row) <= value_idx or not row[sym_idx].strip():
            # Stop at blank region following the table
            # but continue if it's just an empty spacer
            continue
        symbol = row[sym_idx].strip()
        name = row[name_idx].strip() if name_idx < len(row) else ""
        shares = parse_number(row[shares_idx] if shares_idx < len(row) else "0")
        price = parse_number(row[price_idx] if price_idx < len(row) else "0")
        value = parse_number(row[value_idx] if value_idx < len(row) else "0")
        if shares <= 0 and value <= 0:
            continue
        upsert_position(positions, symbol, shares, price, value, name)


def write_position_files(positions: Dict[str, Dict[str, Any]]):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    for tkr, p in positions.items():
        content = (
            f"---\n"
            f"ticker: {p['ticker']}\n"
            f"shares: {p['shares']:.6f}\n"
            f"currentPrice: {p['currentPrice']:.4f}\n"
            f"marketValue: {p['marketValue']:.2f}\n"
            f"costBasis: \n"
            f"assetClass: {p['assetClass']}\n"
            f"lastUpdated: {now}\n"
            f"tags: [position, {p['assetClass']}]\n"
            f"---\n\n"
            f"# Position: {p['ticker']}\n\n"
            f"{p.get('name','')}\n\n"
            f"Current holding of {p['shares']:.6f} shares.\n"
        )
        out_path = STATE_DIR / f"{tkr}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    positions: Dict[str, Dict[str, Any]] = {}
    ubs = PORTFOLIO_DIR / "ubs.csv"
    if ubs.exists():
        import_ubs(ubs, positions)
    vgd = PORTFOLIO_DIR / "vanguard.csv"
    if vgd.exists():
        import_vanguard(vgd, positions)
    if not positions:
        print("No positions parsed.")
        return
    write_position_files(positions)
    total_value = sum(p["marketValue"] for p in positions.values())
    summary_path = STATE_DIR.parent / "portfolio_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# Portfolio Summary\n\nTotal Market Value (parsed): ${total_value:,.2f}\n\nGenerated: {datetime.now().isoformat(timespec='seconds')}\n")
    print(f"Wrote {len(positions)} positions. Total value ~ ${total_value:,.2f}")


if __name__ == "__main__":
    main()

