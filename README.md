
# 📄 TradingBook

**TradingBook**은 _append-only_ CSV 원장에 매수, 매도, 스탑 이동 내역을 기록하고  
해당 로그만으로 현재 포지션, 평균 단가, 리스크, 실현 손익 등을 재현할 수 있는  
초경량 커맨드라인 포트폴리오 트래커입니다.

---

## 1. 설치 및 실행

```bash
# 프로젝트 루트에서 실행
python -m tradingbook.main
# 또는
python src/main.py
````

* 최초 실행 시 `data/` 폴더와 `data/trades.csv` 파일이 자동으로 생성됩니다.
* 외부 패키지 없이 Python 3.9+ 표준 라이브러리만 사용합니다.

---

## 2. 지원 명령어

| 명령어      | 위치 인자                   | 옵션 인자                                            | 설명                            |
| -------- | ----------------------- | ------------------------------------------------ | ----------------------------- |
| `add`    | `TICKER QTY PRICE STOP` | `NOTE`, `--date YYYY-MM-DD`                      | 새로운 매수 트랜치 추가                 |
| `trim`   | `TICKER QTY`            | `--id LOT_ID`, `--price PRICE`, `NOTE`, `--date` | 특정 트랜치에서 일부 매도                |
| `close`  | `TICKER`                | `--id LOT_ID`, `--price PRICE`, `NOTE`, `--date` | 특정 트랜치를 전량 매도 (내부적으로 trim 처리) |
| `stop`   | `TICKER NEW_STOP`       | `--id LOT_ID`, `NOTE`, `--date`                  | 트랜치의 스탑가를 이동                  |
| `split`  | `TICKER`                | `--id LOT_ID`, `--parts "QTY:STOP ..."`, `--date` | 기존 트랜치를 여러 개로 분할            |
| `report` | 없음                      | 없음                                               | 현재 보유 포지션과 실현 손익 요약 출력        |

> 📌 모든 수치(`qty`, `price`, `stop`)는 `Decimal`로 정밀하게 처리됩니다.
> 각 명령어는 CSV에 **새로운 행을 추가**하며, 기존 데이터를 수정하거나 삭제하지 않습니다.

---

## 3. 📝 Note 필드 동작 원리

* 사용자가 `--id LOT_ID` 옵션을 주면, 프로그램이 자동으로 `note` 필드에 `id=LOT_ID` 형식으로 삽입합니다.
* 사용자는 `id=...`를 직접 note에 입력할 필요가 없습니다.
* note에는 원하는 메모를 자유롭게 덧붙일 수 있습니다.

```bash
tb trim QQQ 5 --id 3 --price 445.5 "scalp"
# → 저장되는 note: "trim id=3 scalp"
```

> ❗ CSV를 수동 편집하거나 외부에서 임포트할 경우에는 `id=N` 형식이 정확히 있어야
> 포트폴리오 복원 시 매도 대상 lot이 정확히 매칭됩니다.

---

## 4. 예시 세션

```bash
# 매수
tb add QQQ 10 430.25 418 "setup A"

# 트랜치 3번에서 5주만 매도
tb trim QQQ 5 --id 3 --price 445.50 "partial"

# 트랜치 5번 전량 매도
tb close QQQ --id 5 --price 450.0 "exit all"

# 트랜치 3번 스탑가를 435.0으로 조정
tb stop QQQ 435.0 --id 3 "trail-up"

# 리포트 출력
tb report
```

---

## ✂️ split — 포지션 분할

여러 스탑으로 관리하려는 기존 트랜치를 `split` 명령으로 나눌 수 있다.
`--parts` 옵션에 `수량:STOP` 토큰을 공백으로 나열하면 된다. 첫 토큰은
남길 수량과 새 스탑을 의미하며 나머지는 새로 생성될 트랜치가 된다.

```bash
# lot id=3을 두 파트로 분할
tb split QQQ --id 3 --parts "5:420 5:415"
```

분할 과정은 0원의 실현손익만 발생하므로 이후 `status` 나 `report`로
포지션을 그대로 추적할 수 있다.

---

## 5. 설계 원칙

| 설계 철학                  | 설명                                                       |
| ---------------------- | -------------------------------------------------------- |
| **Append-only 구조**     | 모든 내역이 CSV에 남아 디버깅, 세무, 백테스트에 유리                         |
| **CLI 입력과 CSV 파싱의 분리** | `--id`는 내부적으로 note에 삽입되어 저장되며, 복원 시 note만으로 대상 lot 추적 가능 |
| **Decimal 연산 사용**      | 금융 수치 계산에서 float 오차 없이 정확한 결과 보장                         |
| **명령 = 행 추가**          | 불변성 기반 구조로 리스크 없는 리플레이 & 분석 가능                           |

---
