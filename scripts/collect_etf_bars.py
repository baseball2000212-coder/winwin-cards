# -*- coding: utf-8 -*-
"""ETF 1분봉 수집 — 베이시스(현물 대용)·괴리(iNAV) 연구용.

  229200 KODEX 코스닥150         → 현물 지수 대용 (장중 코스닥150 지수 분봉 대신)
  233740 KODEX 코스닥150레버리지  → 레버리지 ETF 가격·거래량 (괴리·개인 수급)
  251340 KODEX 코스닥150선물인버스 → 인버스 쪽 수급

KIS 주식 일별분봉조회 FHKST03010230 (과거 날짜 지정, 1회 최대 120봉, 보관 약 1년).
오늘부터 과거로 내려가며 받고, 받은 날짜는 건너뛴다. 연속 MAX_MISS 영업일 빈 응답이면 그 종목은 멈춘다.

저장  data/etf_1min/<코드>/YYYYMMDD.csv
실행  PYTHONPATH=scripts python scripts/collect_etf_bars.py   (KQ_START=20251001 등)
"""
import os, csv, time, datetime as dt
import kis

PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
CODES = os.environ.get("ETF_CODES", "229200,233740,251340").split(",")
OUT = "data/etf_1min"
OPEN, CLOSE = "090000", "153000"
TKEY, DKEY = "stck_cntg_hour", "stck_bsop_date"
START = os.environ.get("KQ_START", "20251001")
MAX_MISS = int(os.environ.get("KQ_MAX_MISS", "8"))


def bars(code, ymd):
    rows, hour = [], CLOSE
    for _ in range(6):                      # 390분 ÷ 120 → 4페이지면 충분
        b = kis.fetch(PATH, "FHKST03010230", {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
            "FID_INPUT_HOUR_1": hour, "FID_INPUT_DATE_1": ymd,
            "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": "",
        })
        page = b.get("output2") or []
        if isinstance(page, dict):
            page = [page]
        page = [r for r in page if r.get(TKEY) and r.get(DKEY) == ymd]
        if not page:
            break
        rows.extend(page)
        oldest = min(r[TKEY] for r in page)
        if oldest <= OPEN:
            break
        hour = (dt.datetime.strptime(oldest, "%H%M%S") - dt.timedelta(minutes=1)).strftime("%H%M%S")
        time.sleep(0.12)
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r[TKEY]):
        if r[TKEY] not in seen and OPEN <= r[TKEY] <= CLOSE:
            seen.add(r[TKEY]); out.append(r)
    return out


def main():
    now = kis.now_kst()
    first = now.date() - dt.timedelta(days=0 if now.strftime("%H%M") >= "1540" else 1)
    lo = dt.datetime.strptime(START, "%Y%m%d").date()
    for code in CODES:
        os.makedirs(f"{OUT}/{code}", exist_ok=True)
        day, miss, got = first, 0, 0
        while day >= lo and miss < MAX_MISS:
            if day.weekday() >= 5:
                day -= dt.timedelta(days=1); continue
            ymd = day.strftime("%Y%m%d"); path = f"{OUT}/{code}/{ymd}.csv"
            if os.path.exists(path):
                miss = 0; day -= dt.timedelta(days=1); continue
            try:
                rows = bars(code, ymd)
            except Exception as e:
                rows = []; print(f"[etf] {code} {ymd} 실패: {str(e)[:80]}")
            if rows:
                keys = sorted({k for r in rows for k in r})
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
                miss, got = 0, got + 1
            else:
                miss += 1
            day -= dt.timedelta(days=1)
            time.sleep(0.12)
        print(f"[etf] {code} 신규 {got}일, 멈춘 날짜 {day:%Y%m%d}")


if __name__ == "__main__":
    main()
