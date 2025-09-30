import sys
import csv
from pathlib import Path

def main(in_path: str, out_path: str) -> int:
    in_file = Path(in_path)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with in_file.open(newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "date": r["date"],
                "tenor": r["tenor"],
                "yield": float(r["yield"]),
            })

    # Order tenors for plotting
    order = {"1M":1, "3M":3, "6M":6, "1Y":12, "2Y":24, "3Y":36, "5Y":60, "7Y":84, "10Y":120, "20Y":240, "30Y":360}
    rows.sort(key=lambda x: order.get(x["tenor"], 9999))

    tenors = [r["tenor"] for r in rows]
    yields = [r["yield"] for r in rows]
    date = rows[0]["date"] if rows else ""

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        sys.stderr.write(f"matplotlib not available: {e}\n")
        return 1

    plt.figure(figsize=(8, 4.5), dpi=150)
    plt.plot(tenors, yields, marker="o", linewidth=2, color="#1f77b4")
    for x, y in zip(tenors, yields):
        plt.text(x, y, f" {y:.2f}%", va="bottom", fontsize=8)
    plt.title(f"U.S. Treasury Yield Curve — {date}")
    plt.xlabel("Tenor")
    plt.ylabel("Yield (%)")
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_file)
    return 0

if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "data/yield_curve/latest_us_treasury_curve.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "charts/yield_curve/latest_us_treasury_curve.png"
    raise SystemExit(main(in_path, out_path))

