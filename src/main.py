from __future__ import annotations

import argparse
import csv
import datetime
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Dict, List, Tuple

getcontext().prec = 10

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "trades.csv"
HEADER = ["id", "date", "ticker", "qty", "price", "stop", "note"]


class Lot:
    def __init__(self, lot_id: int, ticker: str, qty: Decimal, price: Decimal, stop: Decimal):
        self.id = lot_id
        self.ticker = ticker
        self.qty = qty
        self.price = price
        self.stop = stop

    def risk(self) -> Decimal:
        return (self.price - self.stop) * self.qty


def ensure_csv() -> None:
    DATA_PATH.parent.mkdir(exist_ok=True)
    if not DATA_PATH.exists():
        with DATA_PATH.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)


def load_rows() -> List[Dict[str, str]]:
    ensure_csv()
    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        return list(reader)


def next_row_id(rows: List[Dict[str, str]]) -> int:
    if not rows:
        return 1
    return max(int(r["id"]) for r in rows) + 1


def append_row(row: Dict[str, str]) -> None:
    with DATA_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writerow(row)


def build_portfolio(rows: List[Dict[str, str]]) -> Tuple[Dict[str, Dict[int, Lot]], Dict[str, Decimal]]:
    positions: Dict[str, Dict[int, Lot]] = {}
    realized: Dict[str, Decimal] = {}

    for r in rows:
        qty = Decimal(r["qty"])
        price = Decimal(r["price"])
        stop = Decimal(r["stop"])
        ticker = r["ticker"]
        row_id = int(r["id"])
        note = r.get("note", "")

        positions.setdefault(ticker, {})
        realized.setdefault(ticker, Decimal("0"))

        if qty > 0:
            # new lot
            positions[ticker][row_id] = Lot(row_id, ticker, qty, price, stop)
        elif qty < 0:
            target = _parse_target_id(note)
            lot = positions[ticker].get(target)
            if not lot:
                continue
            sell_qty = -qty
            if sell_qty > lot.qty:
                sell_qty = lot.qty
            realized[ticker] += sell_qty * (price - lot.price)
            lot.qty -= sell_qty
            if lot.qty == 0:
                del positions[ticker][target]
        else:  # stop move
            target = _parse_target_id(note)
            lot = positions[ticker].get(target)
            if lot:
                lot.stop = stop

    return positions, realized


def _parse_target_id(note: str) -> int:
    for token in note.split():
        if token.startswith("id="):
            try:
                return int(token.split("=", 1)[1])
            except ValueError:
                pass
    raise ValueError("target id not found in note")


def cmd_add(args: argparse.Namespace) -> None:
    rows = load_rows()
    row_id = next_row_id(rows)
    date = args.date or datetime.date.today().isoformat()
    row = {
        "id": str(row_id),
        "date": date,
        "ticker": args.ticker.upper(),
        "qty": str(Decimal(args.qty)),
        "price": str(Decimal(args.price)),
        "stop": str(Decimal(args.stop)),
        "note": args.note or "",
    }
    append_row(row)
    print(f"Added lot {row_id}")


def cmd_trim(args: argparse.Namespace) -> None:
    rows = load_rows()
    row_id = next_row_id(rows)
    date = args.date or datetime.date.today().isoformat()
    note = f"trim id={args.id}" + (f" {args.note}" if args.note else "")
    row = {
        "id": str(row_id),
        "date": date,
        "ticker": args.ticker.upper(),
        "qty": str(-Decimal(args.qty)),
        "price": str(Decimal(args.price)),
        "stop": "0",
        "note": note,
    }
    append_row(row)
    print(f"Trimmed lot {args.id} by {args.qty}")


def cmd_close(args: argparse.Namespace) -> None:
    rows = load_rows()
    positions, _ = build_portfolio(rows)
    ticker = args.ticker.upper()
    lot = positions.get(ticker, {}).get(args.id)
    if not lot:
        print("Lot not found")
        return
    qty = lot.qty
    args_trim = argparse.Namespace(
        ticker=ticker,
        qty=str(qty),
        id=args.id,
        price=args.price,
        note=args.note,
        date=args.date,
    )
    cmd_trim(args_trim)


def cmd_stop(args: argparse.Namespace) -> None:
    rows = load_rows()
    row_id = next_row_id(rows)
    date = args.date or datetime.date.today().isoformat()
    note = f"stop id={args.id}" + (f" {args.note}" if args.note else "")
    row = {
        "id": str(row_id),
        "date": date,
        "ticker": args.ticker.upper(),
        "qty": "0",
        "price": "0",
        "stop": str(Decimal(args.new_stop)),
        "note": note,
    }
    append_row(row)
    print(f"Moved stop for lot {args.id}")


def cmd_report(_: argparse.Namespace) -> None:
    rows = load_rows()
    positions, realized = build_portfolio(rows)

    headers = ["Ticker", "Shares", "AvgIn", "AvgStop", "Risk$", "Realized P/L"]
    print(" | ".join(headers))
    print("-" * 60)
    for ticker, lots in positions.items():
        qty = sum(l.qty for l in lots.values())
        if qty == 0:
            continue
        avg_in = sum(l.qty * l.price for l in lots.values()) / qty
        avg_stop = sum(l.qty * l.stop for l in lots.values()) / qty
        risk = sum(l.risk() for l in lots.values())
        pl = realized[ticker]
        print(
            f"{ticker} | {qty} | {avg_in:.2f} | {avg_stop:.2f} | {risk:.2f} | {pl:.2f}"
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tradingbook")
    sub = p.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="add new lot")
    add_p.add_argument("ticker")
    add_p.add_argument("qty")
    add_p.add_argument("price")
    add_p.add_argument("stop")
    add_p.add_argument("note", nargs="?")
    add_p.add_argument("--date")
    add_p.set_defaults(func=cmd_add)

    trim_p = sub.add_parser("trim", help="trim lot")
    trim_p.add_argument("ticker")
    trim_p.add_argument("qty")
    trim_p.add_argument("--id", required=True, type=int)
    trim_p.add_argument("--price", required=True)
    trim_p.add_argument("note", nargs="?")
    trim_p.add_argument("--date")
    trim_p.set_defaults(func=cmd_trim)

    close_p = sub.add_parser("close", help="close lot")
    close_p.add_argument("ticker")
    close_p.add_argument("--id", required=True, type=int)
    close_p.add_argument("--price", required=True)
    close_p.add_argument("note", nargs="?")
    close_p.add_argument("--date")
    close_p.set_defaults(func=cmd_close)

    stop_p = sub.add_parser("stop", help="move stop")
    stop_p.add_argument("ticker")
    stop_p.add_argument("new_stop")
    stop_p.add_argument("--id", required=True, type=int)
    stop_p.add_argument("note", nargs="?")
    stop_p.add_argument("--date")
    stop_p.set_defaults(func=cmd_stop)

    rep_p = sub.add_parser("report", help="show report")
    rep_p.set_defaults(func=cmd_report)

    return p


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
