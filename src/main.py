


# `__future__ import annotations`는 향후 파이썬에서 타입 힌트를 문자열처럼 처리하게 될 것을 미리 사용하는 옵션이다.
# 이렇게 하면 클래스 내부에서 자기 자신이나 아직 정의되지 않은 타입을 타입 힌트로 쓸 수 있다.
from __future__ import annotations

import argparse # cls 명령어 파싱 모듈
import csv
import datetime
from decimal import Decimal, getcontext # 금융에서 주로 사용하는 고정소수점 모듈
from pathlib import Path
from typing import Dict, List, Tuple

# 고정 소수점 연산인 Decimal의 내부 계산 정밀도를 소수점 12자리까지 보장
getcontext().prec = 12


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


def build_portfolio(rows: List[Dict[str, str]]) -> Tuple[Dict[str, Dict[int, Lot]], Dict[str, Decimal]]:
    """
    반환값 튜플)
    positions: {ticker: {row_id: Lot}} 형태 — 보유 중인 포지션들
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

    print(" | ".join(headers))  # 문자열 리스트를 " | "로 합쳐서 표 형태의 헤더 출력
    print("-" * 60) # "-" * 60"으로 구분선 출력

    for ticker, lots in positions.items():
        # 각 ticker(종목)별로 모든 Lot 객체를 조회
        # 전체 수량이 0이면 (청산 완료된 포지션) → 출력 생략
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


# 이 함수는 argparse.ArgumentParser 객체를 생성해서 리턴함. 즉 CLI 파서 생성기
def build_parser() -> argparse.ArgumentParser:

    p = argparse.ArgumentParser(
    prog="tradingbook",
    description="TradingBook: A CLI-based portfolio tracking tool for stock traders.",
    epilog="""\
    Examples:
    tradingbook add TSLA 100 200 180             # Buy 100 shares of TSLA at 200 with stop at 180
    tradingbook trim TSLA 30 --id 3 --price 220  # Sell 30 shares from lot id=3 at 220
    tradingbook close TSLA --id 3 --price 240    # Close entire position of lot id=3
    tradingbook stop TSLA 190 --id 3             # Move stop to 190 for lot id=3
    tradingbook report                           # Show current positions and realized P/L
    """,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    

    # add, trim, close, stop, report 같은 서브 명령어를 지원하도록 설정
    # dest="command" → 사용자가 입력한 명령어는 args.command에 저장됨
    # required=True → 반드시 하나의 서브 명령어는 입력해야 함
    sub = p.add_subparsers(dest="command", required=True)

    ### add 명령어 정의
    add_p = sub.add_parser("add", help="add new lot")

    # positional argument (필수인자, 반드시 순서를 지켜야 함)
    add_p.add_argument("ticker")
    add_p.add_argument("qty")
    add_p.add_argument("price")
    add_p.add_argument("stop")

    # nargs = "?" : 필수인자지만 생략 가능 (디폴트 매개변수 같은거라 마지막 위치인자에만 사용 가능)
    add_p.add_argument("note", nargs="?")

    # 선택인자 (--arg 사용 시에만 사용, 순서 상관 없고 생략 가능함)
    add_p.add_argument("--date")
    
    # 실행함수 등록
    add_p.set_defaults(func=cmd_add)


    ### trim 명령어 등록
    trim_p = sub.add_parser("trim", help="trim lot")
    trim_p.add_argument("ticker")
    trim_p.add_argument("qty")
    trim_p.add_argument("--id", required=True, type=int) # 선택 인자도 required=True를 주면 사실상 필수로 만들 수 있음
    trim_p.add_argument("--price", required=True)
    trim_p.add_argument("note", nargs="?")
    trim_p.add_argument("--date")
    trim_p.set_defaults(func=cmd_trim)

    # close 명령어 등록
    close_p = sub.add_parser("close", help="close lot")
    close_p.add_argument("ticker")
    close_p.add_argument("--id", required=True, type=int)
    close_p.add_argument("--price", required=True)
    close_p.add_argument("note", nargs="?")
    close_p.add_argument("--date")
    close_p.set_defaults(func=cmd_close)

    # stop 명령어 등록
    stop_p = sub.add_parser("stop", help="move stop")
    stop_p.add_argument("ticker")
    stop_p.add_argument("new_stop")
    stop_p.add_argument("--id", required=True, type=int)
    stop_p.add_argument("note", nargs="?")
    stop_p.add_argument("--date")
    stop_p.set_defaults(func=cmd_stop)

    # report 명령어 등록
    rep_p = sub.add_parser("report", help="show report")
    rep_p.set_defaults(func=cmd_report)

    return p


# argv: 명시적으로 인자 리스트를 넘길 수 있도록 파라미터로 받음
# 기본값은 None. 이 경우 sys.argv를 자동 사용함
def main(argv: List[str] | None = None) -> None:

    print(argv)

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
