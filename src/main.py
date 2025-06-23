


# `__future__ import annotations`는 향후 파이썬에서 타입 힌트를 문자열처럼 처리하게 될 것을 미리 사용하는 옵션이다.
# 이렇게 하면 클래스 내부에서 자기 자신이나 아직 정의되지 않은 타입을 타입 힌트로 쓸 수 있다.
from __future__ import annotations

import argparse # cls 명령어 파싱 모듈
import csv
import datetime
from decimal import Decimal, getcontext # 금융에서 주로 사용하는 고정소수점 모듈
from pathlib import Path
from typing import Dict, List, Tuple

import sys

# 고정 소수점 연산인 Decimal의 내부 계산 정밀도를 소수점 12자리까지 보장
getcontext().prec = 12


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "trades.csv"
HEADER = ["id", "date", "ticker", "qty", "price", "stop", "note"]

def print_status(positions: Dict[str, Dict[int, Lot]]) -> None:
    print("🟢 Open Lots\n")
    for ticker in sorted(positions.keys()):
        lots = positions[ticker]
        for lot in lots.values():
            print(
                f"[{ticker:<5}] Lot ID={lot.id} | Qty={lot.qty} | "
                f"In={lot.price:.2f} | Stop={lot.stop:.2f} | "
                f"Risk=${lot.risk():.2f}"
            )


def print_report(positions: Dict[str, Dict[int, Lot]], realized: Dict[str, Decimal]) -> None:
    print("\n📊 Portfolio Summary (by Ticker)\n")
    print("Ticker | Shares | AvgIn | AvgStop | Risk$ | Realized P/L")
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
            f"{ticker:<6} | {qty} | {avg_in:.2f} | {avg_stop:.2f} | {risk:.2f} | {pl:.2f}"
        )



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
        reader = csv.DictReader(f) # 첫 줄을 헤더로 인식하고, 이후 각 줄을 dict로 반환하는 이터레이터 객체
        return list(reader) # 이터레이터를 강제로 모두 소비하여, 각 줄을 딕셔너리로 변환한 리스트 반환




def next_row_id(rows: List[Dict[str, str]]) -> int:
    if not rows:
        return 1
    return max(int(r["id"]) for r in rows) + 1

"""
"a": append 모드 — 기존 파일 내용을 유지하면서 맨 끝에 추가
newline="": 윈도우 환경에서 불필요한 빈 줄 생김 방지 (표준 권장)
"""
def append_row(row: Dict[str, str]) -> None:
    with DATA_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writerow(row)


def make_row(row_id: int, date: str, ticker: str, qty: Decimal,
             price: Decimal, stop: Decimal, note: str) -> Dict[str, str]:
    """공용 row 생성 헬퍼"""
    return {
        "id": str(row_id),
        "date": date,
        "ticker": ticker,
        "qty": str(qty),
        "price": str(price),
        "stop": str(stop),
        "note": note,
    }


def build_portfolio(rows: List[Dict[str, str]]) -> Tuple[Dict[str, Dict[int, Lot]], Dict[str, Decimal]]:
    """
    반환값 튜플)
    positions: {ticker: {row_id: Lot}} 형태 — 보유 중인 \n
    realized: {ticker: 수익} 형태 — 실현 수익금
    """

    positions: Dict[str, Dict[int, Lot]] = {}
    realized: Dict[str, Decimal] = {}   

    for r in rows:
        # csv 읽은 값은 기본적으로 str이기 때문에 Decimal로 변환 필요
        qty = Decimal(r["qty"])
        price = Decimal(r["price"])
        stop = Decimal(r["stop"])
        ticker = r["ticker"]
        row_id = int(r["id"])
        note = r.get("note", "")

        # dict에 키 없으면 기본값 세팅
        positions.setdefault(ticker, {})
        realized.setdefault(ticker, Decimal("0"))



        # csv 에서 qty가 양수이면 매수 입력, 음수이면 매도 입력, 0이면 그 밖의 처리(move stop) 
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
                return int(token.split("=", 1)[1]) # '=' 기준으로 1번 쪼개서 [1] 인덱스를 반환
            except ValueError:
                pass
    raise ValueError("target id not found in note")


def cmd_add(args: argparse.Namespace) -> None:
    rows = load_rows()
    row_id = next_row_id(rows)
    date = args.date or datetime.date.today().isoformat() # date 인자가 없으면 오늘 날짜 사용.

    # csv 저장되기 위한 형태는 반드시 str
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
    positions, _ = build_portfolio(rows)

    ticker = args.ticker.upper()
    lot = positions.get(ticker, {}).get(args.id)

    # 1) ID 존재 검사
    if not lot:
        print(f"⚠️ Trim skipped: lot id={args.id} for {ticker} not found.")
        return

    sell_qty = Decimal(args.qty)
    # 2) 과다 매도 방지
    if sell_qty > lot.qty:
        print(f"⚠️ Trim skipped: trying to sell {sell_qty}, but only {lot.qty} left.")
        return

    # 3) 정상 처리
    row_id = next_row_id(rows)
    date = args.date or datetime.date.today().isoformat()
    note = f"trim id={args.id}" + (f" {args.note}" if args.note else "")
    row = {
        "id": str(row_id),
        "date": date,
        "ticker": ticker,
        "qty": str(-sell_qty),
        "price": str(Decimal(args.price)),
        "stop": "0",
        "note": note,
    }
    append_row(row)
    print(f"Trimmed lot {args.id} by {sell_qty}")


def cmd_close(args: argparse.Namespace) -> None:
    rows = load_rows()
    positions, _ = build_portfolio(rows)

    ticker = args.ticker.upper()
    lot = positions.get(ticker, {}).get(args.id)


    if not lot:
        print(f"⚠️ Close skipped: lot id={args.id} for {ticker} not found.")
        return
    if lot.qty == 0:
        print(f"⚠️ Close skipped: lot id={args.id} for {ticker} already fully sold.")
        return
    
    # close는 특정 트랜치를 전량 청산하는 것을 의미하기 때문에 id가 일치하는 트랜치의 전체 수량을 cmd_trim 입력으로 넣어 코드를 재사용한다.
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
    positions, _ = build_portfolio(rows)

    ticker = args.ticker.upper()
    lot = positions.get(ticker, {}).get(args.id)
    
    if not lot:
        print(f"⚠️ Stop skipped: lot id={args.id} for {ticker} not found.")
        return

    row_id = next_row_id(rows)
    date = args.date or datetime.date.today().isoformat()
    note = f"stop id={args.id}" + (f" {args.note}" if args.note else "")
    row = {
        "id": str(row_id),
        "date": date,
        "ticker": ticker,
        "qty": "0",
        "price": "0",
        "stop": str(Decimal(args.new_stop)),
        "note": note,
    }
    append_row(row)
    print(f"Moved stop for lot {args.id} of {ticker}: {lot.stop} ➝ {args.new_stop}")


def cmd_split(args: argparse.Namespace) -> None:
    rows = load_rows()
    positions, _ = build_portfolio(rows)

    ticker = args.ticker.upper()
    lot = positions.get(ticker, {}).get(args.id)

    if not lot or lot.qty == 0:
        print(f"⚠️ Split skipped: lot id={args.id} for {ticker} not found or closed.")
        return

    tokens = args.parts.split()
    parts: List[Tuple[Decimal, Decimal]] = []
    for tok in tokens:
        try:
            qty_s, stop_s = tok.split(":", 1)
            parts.append((Decimal(qty_s), Decimal(stop_s)))
        except Exception:
            print(f"⚠️ Split skipped: invalid part '{tok}'.")
            return

    total_qty = sum(q for q, _ in parts)
    if total_qty != lot.qty:
        print(f"⚠️ Split skipped: parts sum {total_qty} ≠ lot qty {lot.qty}.")
        return

    stops = [s for _, s in parts]
    if len(stops) != len(set(stops)):
        print("⚠️ Split skipped: duplicate stop values.")
        return

    date = args.date or datetime.date.today().isoformat()
    row_id = next_row_id(rows)
    total_rows = len(parts) + 1
    idx = 1

    # A. trim
    trim_qty = lot.qty - parts[0][0]
    note = f"split from id={args.id} part {idx}/{total_rows}"
    rows_to_append = [
        make_row(row_id, date, ticker, -trim_qty, lot.price, Decimal("0"), note)
    ]
    row_id += 1
    idx += 1

    # B. stop move for original lot
    note = f"split from id={args.id} part {idx}/{total_rows}"
    rows_to_append.append(
        make_row(row_id, date, ticker, Decimal("0"), Decimal("0"), parts[0][1], note)
    )
    row_id += 1
    idx += 1

    # C. add new lots
    for qty, stop in parts[1:]:
        note = f"split from id={args.id} part {idx}/{total_rows}"
        rows_to_append.append(
            make_row(row_id, date, ticker, qty, lot.price, stop, note)
        )
        row_id += 1
        idx += 1

    for r in rows_to_append:
        append_row(r)
    print(f"Split lot {args.id} of {ticker} into {len(parts)} parts")
    

def cmd_status(_: argparse.Namespace) -> None:
    rows = load_rows()
    positions, _ = build_portfolio(rows)
    print_status(positions)


def cmd_report(_: argparse.Namespace) -> None:
    rows = load_rows()
    positions, realized = build_portfolio(rows)
    print_report(positions, realized)


def cmd_summary(_: argparse.Namespace) -> None:
    rows = load_rows()
    positions, realized = build_portfolio(rows)
    print_status(positions)
    print_report(positions, realized)

# 이 함수는 argparse.ArgumentParser 객체를 생성해서 리턴함. 즉 CLI 파서 생성기
def build_parser() -> argparse.ArgumentParser:

    p = argparse.ArgumentParser(
    prog="tradingbook",
    description="TradingBook: A CLI-based portfolio tracking tool for stock traders.",
    epilog="""\
    Examples:
    tradingbook add TSLA 100 200 180                         # Buy 100 shares @200, stop 180
    tradingbook trim TSLA 30 --id 3 --price 220              # Sell 30 shares from lot id=3 @220
    tradingbook close TSLA --id 3 --price 240                # Close entire lot id=3 @240
    tradingbook stop TSLA 190 --id 3                         # Move stop of lot id=3 to 190
    tradingbook split TSLA --id 3 --parts "50:190 50:185"    # Split lot id=3 into two tranches
    tradingbook status                                        # Show all open lots (ID-level view)
    tradingbook report                                        # Show ticker-level portfolio summary
    tradingbook summary                                       # status + report in one shot
    """,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    

    # add, trim, close, stop, report 같은 서브 명령어를 지원하도록 설정
    # dest="command" → 사용자가 입력한 명령어는 args.command에 저장됨
    # required=True → 반드시 하나의 서브 명령어는 입력해야 함
    sub = p.add_subparsers(dest="command", required=True)

    ### add 명령어 정의
    add_p = sub.add_parser("add", help="Add a new lot (buy)")
    # positional argument (필수인자, 반드시 순서를 지켜야 함)
    add_p.add_argument("ticker", help="Stock ticker symbol (e.g., TSLA)")
    add_p.add_argument("qty", help="Number of shares to buy (e.g., 100)")
    add_p.add_argument("price", help="Entry price per share (e.g., 200.0)")
    add_p.add_argument("stop", help="Initial stop loss price (e.g., 180.0)")

    add_p.add_argument("--note", help="Optional memo or trade note")
    # 선택인자 (--arg 사용 시에만 사용, 순서 상관 없고 생략 가능함)
    add_p.add_argument("--date", help="Transaction date (YYYY-MM-DD). Defaults to today.")    
    # 실행함수 등록
    add_p.set_defaults(func=cmd_add)


    ### trim 명령어 등록
    trim_p = sub.add_parser("trim", help="Sell part of a lot (partial exit)")

    trim_p.add_argument("ticker", help="Stock ticker (e.g., TSLA)")
    trim_p.add_argument("qty", help="Quantity to sell (e.g., 30)")
    trim_p.add_argument("--id", required=True, type=int, help="Target lot ID to trim from")
    trim_p.add_argument("--price", required=True, help="Sell price (e.g., 220.5)")
    trim_p.add_argument("--note", help="Optional memo or trade note")
    trim_p.add_argument("--date", help="Execution date (YYYY-MM-DD)")
    trim_p.set_defaults(func=cmd_trim)


    # close 명령어 등록
    close_p = sub.add_parser("close", help="Close an entire lot (full exit)")

    close_p.add_argument("ticker", help="Stock ticker (e.g., TSLA)")
    close_p.add_argument("--id", required=True, type=int, help="Lot ID to close")
    close_p.add_argument("--price", required=True, help="Sell price for closing (e.g., 240.0)")
    close_p.add_argument("--note", help="Optional memo or trade note")
    close_p.add_argument("--date", help="Execution date (YYYY-MM-DD)")
    close_p.set_defaults(func=cmd_close)


    # stop 명령어 등록
    stop_p = sub.add_parser("stop", help="Move stop loss for a specific lot")

    stop_p.add_argument("ticker", help="Stock ticker (e.g., TSLA)")
    stop_p.add_argument("new_stop", help="New stop loss price (e.g., 190.0)")
    stop_p.add_argument("--id", required=True, type=int, help="Lot ID to update stop for")
    stop_p.add_argument("--note", help="Optional memo or trade note")
    stop_p.add_argument("--date", help="Execution date (YYYY-MM-DD)")
    stop_p.set_defaults(func=cmd_stop)

    # split 명령어 등록
    split_p = sub.add_parser("split", help="Split a lot into multiple lots")
    split_p.add_argument("ticker", help="Stock ticker (e.g., TSLA)")
    split_p.add_argument("--id", required=True, type=int, help="Lot ID to split")
    split_p.add_argument(
        "--parts",
        required=True,
        help="Parts as 'QTY:STOP' tokens separated by space",
    )
    split_p.add_argument("--note", help="Optional memo or trade note")
    split_p.add_argument("--date", help="Execution date (YYYY-MM-DD)")
    split_p.set_defaults(func=cmd_split)


    # report 명령어 등록
    rep_p = sub.add_parser("report", help="Display portfolio summary and P/L report")
    rep_p.set_defaults(func=cmd_report)


    # status 명령어 등록
    stat_p = sub.add_parser("status", help="Display all currently open lots")
    stat_p.set_defaults(func=cmd_status)

    # summary 명령어 등록
    sum_p = sub.add_parser("summary", help="Show both status and report")
    sum_p.set_defaults(func=cmd_summary)

    return p


# argv: 명시적으로 인자 리스트를 넘길 수 있도록 파라미터로 받음
# 기본값은 None. 이 경우 sys.argv를 자동 사용함
def main(argv: List[str] | None = None) -> None:

    # CLI 파서 생성
    parser = build_parser() 

    # 인자 실제로 파싱해서 네임스페이스 객체로 반환
    # ex) tradingbook add TSLA 100 200 180
    # 이걸 아래처럼 
    #    args = Namespace(
    #       command="add",
    #       ticker="TSLA",
    #       qty="100",
    #       price="200",
    #       stop="180",
    #       note=None,
    #       func=cmd_add
    #    )
    args = parser.parse_args(argv) 

    # 여기서 CLI 명령이 실제로 실행됨
    args.func(args)


if __name__ == "__main__":
    main()
