# -*- coding: utf-8 -*-
"""수집본이 올라올 때까지 기다린다.

  python3 cards/wait_data.py us 0650 15     오늘 06:50 KST 이후 수집본을 최대 15분 기다림
  python3 cards/wait_data.py kr 1600 20

받으면 cards/out/data_<kind>.json 에 저장하고 asof_kst를 출력한다. 못 받으면 exit 1.
"""
import sys, time, json
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import kit

kind, after, minutes = sys.argv[1], sys.argv[2], int(sys.argv[3])
deadline = time.time() + minutes * 60
while True:
    try:
        d = kit.fetch(kind)
        asof = d.get("asof_kst", "")
        today = kit.now_kst().strftime("%Y-%m-%d")
        if asof[:10] == today and asof[11:16].replace(":", "") >= after:
            print("OK", asof, "errors:", d.get("errors"))
            sys.exit(0)
        print("아직 이전 수집본:", asof, flush=True)
    except Exception as e:
        print("받기 실패:", e, flush=True)
    if time.time() > deadline:
        print("TIMEOUT — 수집본이 안 올라옴")
        sys.exit(1)
    time.sleep(30)
