# TradingBook

A minimal command-line portfolio tracker using an append-only CSV ledger.

## Usage

Initialize the data folder and run commands with `python -m tradingbook.main` or `python src/main.py`.

### Commands

- `add TICKER QTY PRICE STOP [NOTE]`
- `trim TICKER QTY --id LOT_ID --price PRICE [NOTE]`
- `close TICKER --id LOT_ID --price PRICE [NOTE]`
- `stop TICKER NEW_STOP --id LOT_ID [NOTE]`
- `report`

All monetary values and quantities are handled with `Decimal` for precision. Each command appends a new row to `data/trades.csv`.

