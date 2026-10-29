# winwin_macro 카드뉴스 실행 지침

예약 작업이 이 세션을 깨우면 이 문서를 읽고 해당 덱을 끝까지 만든다. 사용자는 보고 있지 않다. 질문하지 말고 끝까지 완수한다.
원본은 사용자가 Cowork에서 쓰던 지침(10/19 확정)이다. 여기에는 이 환경에 맞게 필요한 것만 남겼다.

| 덱 | 예약 시각 | 전달 목표 | 발행 | content `deck` |
|---|---|---|---|---|
| 미장 마감 | 화~토 07:05 | 07:40 | **08:00 자동 발행** | `us` |
| 장중 파생 | 평일 12:57 | 13:20 | **13:30 자동 발행** (사용자 요청 10/29) | `kr_live` |
| 국장 마감 | 평일 16:06 | 16:20 | **16:30 자동 발행** | `kr_close` |

**목표 시각은 마감이 아니다.** 늦어져도 절대 건너뛰지 말고 끝까지 만들어 전달하고 발행한다. 발행 시각이 지났으면 지금부터 5분 뒤로 예약한다.
순서는 반드시: 데이터 → 리서치 → 카드 → **전달** → 발행. 전달보다 발행을 먼저 하지 않는다.

---

## 0. 준비

```bash
cd /home/user/kis-data && bash cards/setup.sh          # matplotlib·폰트 (이미 있으면 건너뜀)
[ -d /home/user/winwin-cards/.git ] || git clone -q https://github.com/baseball2000212-coder/winwin-cards /home/user/winwin-cards 2>/dev/null || true  # 카드 이미지용 공개 저장소
TZ=Asia/Seoul date '+%Y-%m-%d %a %H:%M'                 # 날짜·요일은 반드시 셸로 확인. 추측 금지
```
- 데이터 기준일 요일도 `date -d YYYY-MM-DD '+%a'`로 확인한다.
- 한국 휴장일이면(장중·국장 덱) 카드 대신 "휴장 — 종료" 한 줄만 남기고 끝낸다. 미국 휴장 다음 날 아침(미장 덱)은 표지에 휴장을 밝히고 주간 프리뷰 4장으로 대체한다.

## 1. 데이터 (유일한 수치 출처)

```bash
python3 cards/wait_data.py us 0650 15     # 미장: 오늘 06:50 이후 수집본
python3 cards/wait_data.py kr 1250 15     # 장중: 12:50 이후
python3 cards/wait_data.py kr 1600 15     # 국장: 16:00 이후 (16:03 확정치 재수집본)
python3 cards/kit.py facts us|kr          # 카드에 쓸 수치 계산 결과
python3 cards/kit.py pc                   # P/C 5영업일 추이 (kr)
```
- TIMEOUT이면 `mcp__github__actions_run_trigger`(run_workflow, owner `baseball2000212-coder`, repo `kis-data`, ref `main`, workflow `collect-us.yml` / `collect-kr.yml`)로 수집을 다시 돌리고 10분 더 기다린다. 그래도 없으면:
  - 미장: 경로 차트 카드를 빼고 리서치 수치로만 만든다. 마지막 메시지에 알린다.
  - 장중: 장중 수치를 지어내지 말고 "collect-kr 워크플로가 안 돌았다"고 알리고 카드는 만들지 않는다.
  - 국장: 분봉 차트를 빼고 확인된 수치로만 만든다. 마지막 메시지에 알린다.
- `errors`가 비어 있지 않으면 내용을 확인하고, 관련 카드를 뺀다.
- 시가·고가·저가·종가·등락률·고점/저점 시각은 전부 `facts` 출력에서 가져온다. 기사 수치와 섞지 않는다. 미국 지수의 종가·등락률은 `close_api`·`pct_api`를 쓴다.
- **쓰면 안 되는 키**: `investor_time_REF_ONLY`(부호 반대 사고), `stocks.*.last`·`last_chg_pct`(국장 덱에서는 시간외가 섞임. 장중 덱에서는 장중 값이라 써도 된다), `fx`(국장 카드 수치로 쓰지 말고 참고만).
- 옵션 수치는 `option_source == "chain"`이고 `center_src == "실시간"`일 때만 쓴다. 아니면 옵션 카드를 통째로 뺀다.
- `future_is_mini`가 true면 "코스피200 선물(미니)", false면 "코스피200 선물".

**수급 대조(국장·장중 필수)**: 개인·외국인·기관 순매수를 웹 시황과 대조한다(카드에는 표시하지 않는다). 방향이 다르거나 30% 넘게 벌어지면:
- 국장: 16:10 이전 커밋본으로 다시 대조한다. `git fetch -q origin main && git log origin/main --format='%H %s' -n 10 -- data/kr/latest.json`에서 메시지 "kr YYYY-MM-DD HH:MM"의 시각이 16:10 이하인 가장 늦은 sha를 골라 `python3 cards/kit.py fetch kr <sha>`. (kis-data는 비공개일 수 있으니 공개 주소·GitHub API 대신 git을 쓴다.) 그래도 안 맞으면 수급 카드를 통째로 뺀다. (16:00 이후 수집본은 시간외가 더해져 부호까지 뒤집힌 적이 있다.)
- 장중: 수급 카드를 통째로 뺀다.

## 2. 리서치 (WebSearch / WebFetch)

기사는 **"왜 움직였나"만** 담당한다. 미장 15분, 장중 10분, 국장 20분 안에 끝낸다. 확인 안 된 수치는 지어내지 않고 뺀다.
- **전환 시점의 원인(필수)**: `facts`의 고점·저점 시각에 무슨 일이 있었는지 찾는다. 못 찾으면 시각·수치만 쓴다(추측 금지).
- 관심도: Investing.com Most Popular, Stocktwits 트렌딩, Yahoo Finance top stories 상위 1~2개를 표지 제목·원인 문장에 반영한다.
- 미장 **시간외(필수, 사용자 요청 10/29)**: 장 마감 후 실적 발표 종목의 시간외 등락과 그 뒤 나스닥100·S&P 선물 방향을 반드시 확인한다. 한국 아침에 시장을 움직이는 건 정규장 종가가 아니라 이 흐름이다. 시간외 움직임이 크면(대형주 ±5% 이상, 지수 선물이 정규장과 반대 방향 등) 표지 제목·실적 카드·관전포인트·캡션의 중심을 시간외 쪽으로 옮기고, 실적 카드는 장중 흐름 바로 뒤(2~3번째)에 둔다. 정규장 수치는 지수 줄·타일에 그대로 둔다.
- 미장: 미 2년·10년물과 bp 변동, 2s10s, 연준 목표범위 대비 2년물 → 내재 인하 횟수(직접 계산), DXY·USD/JPY·WTI·금, 다음 FOMC(KST)와 내재 확률 3~5개 시점, 위원 발언(발언자 이름은 가능), 밤사이 지표 vs 컨센, 이번 주 일정(KST: 서머타임 +13h, 표준시 +14h), 국내 만기·금통위, 전일 국장 마감·외국인 수급, 반도체(SOX·마이크론·엔비디아), USD/KRW 역외 NDF.
- 장중: 미국 지수 선물이 지금 움직이면 그게 실시간 원인 신호다(반드시 확인). 월요일이면 주말 사건부터. 오전 중 꺾인 시각 근처 헤드라인.
- 국장: 섹터 6개(반도체·이차전지·자동차·방산·조선해운·원전) 등락은 JSON `sectors`, 웹에서는 이유만. 평균 1위가 스포트라이트(전부 하락이면 가장 덜 빠진 섹터). 이유가 없으면 "수급 주도". 환율: USD/KRW 서울 15:30 종가·변동·장중 범위, USD/JPY, 100엔(= USD/KRW ÷ USD/JPY × 100 직접 계산), 달러인덱스를 웹 2곳 이상에서 확인. 오늘 밤·이번 주 일정, 선물옵션 만기(둘째 목요일)·금통위.
- 네이버 금융·Reddit·Yahoo 차트 API는 막혀 있으니 시도하지 않는다.
- 아주 최근 뉴스는 검색 결과가 빈약할 때가 있다. 그럴 땐 그 줄을 빼고 차트·표를 키운다.

## 3. 문장 규칙 — 비유 금지, 직접적으로 (다른 모든 규칙보다 우선)

- 제목·부제·콜아웃·불릿·타임라인·말풍선 전부 **사실을 그대로** 쓴다. 비유·은유·문학적 표현·수수께끼 같은 압축 문장 금지. 처음 보는 사람이 한 번 읽고 알아들어야 한다.
- 제목에는 **대상과 숫자**(무엇이 · 얼마나 · 어떻게). 질문형·부정형 금지. 기준·대상을 생략하지 않는다. 2줄 이내, 의미 단위로 끊는다.
- 나쁜 예 → 좋은 예: "문은 한쪽만 열려 있다" → "9월 금리 인하 확률이 35%로 떨어졌다" / "美 반도체 8연패가 판 구덩이" → "미국 반도체 지수 8거래일 연속 하락" / "개인이 던진 1조 932억, 누가 받았나" → "개인 1조 932억 순매도, 기관 5,760억 순매수" / "숏커버 반등이 아니었다" → "K200 선물 상승에 신규 매수가 들어왔다" / "885에서 멈출까, 900을 두드릴까?" → "콜옵션 미결제가 가장 많은 행사가는 900" / "주식이 흔들려도 원화는 강해졌다" → "원달러 1,330.3원, 2년 만에 최저 수준"
- 전문용어는 쉬운 말로 풀거나 부제에서 바로 설명한다("콜벽" 대신 "콜옵션 미결제가 가장 많은 900"). 체크 항목은 "~여부" 명사형, 관전포인트는 "IF … → …" 조건문.
- 표지 제목은 원인을 앞에 두되 직접적으로. 검색 키워드(미장: 미국증시·나스닥·연준·국채금리 / 국장: 코스피·환율·외국인)를 자연스럽게 넣는다.

## 4. 어투 규칙 — 기사를 인용하는 티를 내지 마라

- 매체명 일체 금지(로이터·블룸버그·CNBC·연합인포맥스·이데일리·네이버 등). 차트·푸터 어디에도.
- 인용·전언 금지: "~에 따르면", "~라고 전했다", "~로 알려졌다", "보도됐다", "전망된다", "~라는 분석이 나온다", "시장에서는 ~라는 평가".
- 전문가 인용 금지: "○○증권 연구원은", "한 시장 관계자는", "딜러들은".
- 소싱 사정 노출 금지: "자료 미공개", "확인되지 않음", "집계 전", "—" 빈칸.
- 사실은 단정형으로, 사건 자체를 주어로. 못 구한 값은 그 줄을 통째로 빼고 남은 요소를 키운다.
- "HH:MM 기준", "장중", "오전 누적"은 허용. ADR 가격 차이는 "프리미엄".
- 파생·옵션 관점 코멘트는 미장 덱에 넣지 않는다(매크로 → 금리 → 주식 사슬만).

## 5. 카드 만들기

그날 문구를 `cards/out/content_<deck>.json`에 쓰고 빌드한다. 틀은 `cards/examples/us.json`, `kr_close.json`, `kr_live.json`(문구는 전부 새로 쓴다).
```bash
python3 cards/kit.py build cards/out/content_us.json
```
- 출력의 `WARN` 줄(넘침·잘림·제목 3줄)은 전부 고친다. 고친 뒤 다시 빌드.
- 빌드 후 **PNG를 Read로 직접 본다**(표지 + 각 카드). 말풍선과 선의 겹침, 하단 빈 공간, 등락 숫자 색(상승 빨강·하락 파랑), 한 줄 문장이 1~2단어만 넘어가는지 확인하고 고친다.
- 디자인(SayDay 톤, 색, 폰트, 상단 줄, 배지, 페이지 표시)은 코드에 고정돼 있다. 바꾸지 않는다.
- 카드당 요소 3종류까지, 불릿 최대 2개(국장 마감 덱의 장중 흐름·투자자 카드는 3개). 콜아웃은 지정된 카드에만.
- 장수 6~8장. 차트가 하나도 없는 덱은 안 된다.

### 카드 종류 (`type`)
공통: `section`(상단 줄 섹션명), `badge`(`us` 미국 주식 / `macro` 매크로 / `spot` 현물 / `deriv` 선물·파생 / 생략=배지 없음), `title`(줄 배열, 2줄 이내), `sub`(회색 부제), `bullets`, `callout`({label, lines[], minor[]}), `skip: true`면 제외.
- `cover` — title, index_line {text, dir(+1/−1/0)}, desc, chips[3], meta, tiles[{label, value, chg, dir}] 3~4칸, mini {series, label, until}
- `path` — series(`NDX` `QQQ` `SPX` `SPY` `NVDA` `KOSPI` `KOSDAQ` `FUT`), hi_text·lo_text(말풍선, `\n`으로 2줄), until("13:05" 장중), now_text("13:05 현재"), timeline[{time, head, desc}], header {ticker, desc, value, dir}
- `bars` — source `investors`(flow_check_eok) / `program`(program_check_eok) / 직접 {cats, vals, unit}, header
- `hbars` — source `stocks12`(정규장 종가 등락률) / 직접 {cats, vals}
- `lines` — labels[], series[{name, vals, color(navy|blue|red|orange), texts[], below}], ref {value, label}, header, label_right(false면 오른쪽 이름표 없음)
- `keyvals` — rows[{label, value, note, dir}], chart(선택: path와 같은 필드)
- `table` — rows[{when, event, desc, key}]
- `points` — bullets(박스 안에 퍼짐), keyvals(선택), callout
- `sector` — spotlight {sector, why[2줄]}, reasons {섹터: 한 줄 이유}, callout
- `pc` — P/C 5영업일 추이(자동, 3점 미만이면 생략됨), bullets
- `meme` — 밈 카드(사용자 요청 10/29). format `drake`: rows[{emoji, label, text, desc, no}] (no=true 줄은 회색·취소선, "시장이 넘긴 것 / 시장이 본 것") / format `vs`: cols[{label, emoji, text, dir, desc}] 2칸("기대 / 현실"), callout 선택

### 밈 카드 규칙
- 그날 숫자끼리 뚜렷한 대비가 있을 때만(예: 실적은 좋은데 주가 급락, 지표는 서프라이즈인데 금리 급등) 덱마다 **최대 1장**, 마지막 카드 바로 앞에 넣는다. 억지로 만들지 않는다.
- 그림은 **이모지만** 쓴다. 실제 밈 사진·만화 캡처·연예인/인물 사진·로고는 저작권 문제로 쓰지 않는다.
- 재미는 형식(대비 구도)과 이모지로만 낸다. 글자는 3장 문장 규칙 그대로: 대상과 숫자를 넣고 사실을 직접 쓴다. 비꼬기·조롱·특정인 비하 금지.

### 덱별 구성
**미장 마감(us)** — 6장 기본, 필요하면 7~8장
1. 표지: tiles = S&P 500 / 나스닥100 / VIX / 미 10년물, mini = NDX
2. 장중 흐름(`path`, NDX 5분봉 — 전일 종가 점선이 있어서 기본값; QQQ 1분봉을 쓰면 전일 종가 점선 없음) + 타임라인 2개(시각 + 헤드라인 + 부연 한 줄). 그 카드의 수치는 차트 지수 기준으로만. 다우는 다루지 않는다.
3. 국채(`lines`, macro): 2년·10년물 점 연결 + 기준금리 점선, 점마다 수치·bp. 불릿 2개
4. 연준(`lines`, macro): 다음 FOMC 확률 추이 3~5점, 50% 점선. 불릿 2개
5. 이번 주 일정(`table`, 배지 없음) 5행, 핵심 행 강조
6. 오늘 국장 관전포인트(`points`): 불릿 3개(밤사이 미국·반도체 → 갭 방향, 외국인 수급, 환율) + 콜아웃 "한 줄"(이 카드에만)
(관심 이슈·개별 종목 카드가 필요하면 5번 앞에)

**장중 파생(kr_live)** — "지금 파생 쪽에서 누가 무슨 포지션을 잡고 있나". 마감 카드와 같은 이야기를 반복하지 않는다. `asof_label`: "HH:MM 기준"
1. 표지: chips 예 "외국인 선물 +3,200계약", "비차익 +5,240억", "P/C 1.77" / tiles 코스피·K200 선물·베이시스·외국인 현물 / mini KOSPI until
2. 코스피 오전 경로(`path`, spot, until, now_text) 말풍선 2개
3. 현물 수급(`bars` investors, spot) 부제에 "오전 누적". 불릿 2개
4. 차익 vs 비차익(`bars` program, deriv) + 콜아웃(비차익이 크면 방향성 매매, 차익이 크면 기계적 재정거래)
5. 선물 포지션(`keyvals` + chart FUT, deriv): position_read, 미결제 증감, 베이시스·괴리율
6. 옵션(`keyvals`, deriv) — 옵션 조건을 만족할 때만: P/C OI, 콜·풋 최대 OI 행사가, ATM IV
7. P/C 5영업일 추이(`pc`, deriv) — 불릿: ① 정점이 언제, 그날 무슨 일 ② 비율 변화가 콜 때문인지 풋 때문인지
8. 오후 관전포인트(`points`): 불릿 2개 "IF … → …"(단정하지 않는다) + 콜아웃 "오후 체크" 2줄("~여부")
**현물 수급과 선물 수급을 한 장에 섞지 않는다.**

**국장 마감(kr_close)** — 8장 기본
1. 표지: tiles 코스피·코스닥·USD/KRW·100엔, mini KOSPI
2. 장중 흐름(`path` KOSPI, spot) + 불릿 3개(오전·오후·업종)
3. 투자자별 순매수(`bars` investors, spot) + 불릿 3개(기관 세부 — facts의 investor_detail_eok, 외국인 연속 매매 — foreign_streak). 대조 통과한 숫자만
4. K200 선물(`keyvals` + chart FUT, deriv): 미결제·베이시스·P/C·ATM 변동성. 10분 안에 확실히 안 잡히면 뺀다
5. 섹터(`sector`, spot), 섹션명 "섹터 · 6개 중 오늘 1등" + 콜아웃 "한 줄"
6. 대장주 12종목(`hbars` stocks12, spot)
7. 환율(`keyvals`, spot): USD/KRW, 장중 범위, 100엔, USD/JPY, 달러인덱스 + 불릿 2개
8. 오늘 밤·이번 주(`table`) + 콜아웃 "내일 아침 체크" 2줄

## 6. 캡션

이모지 없이 평서체("~했다"), 3·4장 규칙 그대로. content의 `caption`에 넣는다(빌드하면 caption.txt로 저장).
- **미장**: "[M/D 요일 미국증시 마감] " + 표지 제목 / 빈 줄 / 핵심 수치 2줄(S&P·나스닥100 / 미 10년물·2년물·VIX) / 빈 줄 / 밤사이 원인–결과 3문장 이내 / 빈 줄 / 오늘 국장 관전포인트 2~3문장 / 빈 줄 / "이번 주: A → B → C" / 빈 줄 / "데이터: 한국투자증권 Open API (미국 본장 분봉)" / 빈 줄 / 해시태그 정확히 5개: #주식공부 #미국주식 #연준 + 2개(#국채금리 #FOMC #CPI #나스닥 #환율 #반도체 #유가 #관세 중)
- **국장**: "[M/D 요일 코스피 마감] " + 표지 제목 / 빈 줄 / 핵심 수치 2줄(코스피·코스닥 / USD/KRW·100엔) / 빈 줄 / 원인–결과 3문장 이내 / 빈 줄 / "오늘 섹터 1등: ○○ +x.x%" + 6개 섹터 등락 한 줄 + 콜아웃 문장 / 빈 줄 / 가장 중요한 관점 하나 2~3문장 / 빈 줄 / "이번 주: A → B → C" / 빈 줄 / "데이터: 한국투자증권 Open API (코스피 분봉·투자자별 순매수)" / 빈 줄 / 해시태그 정확히 5개: #주식공부 #코스피 #환율 + 그날 1등 섹터 태그 2개(#반도체 #이차전지 #자동차주 #방산주 #조선주 #원전주 #외국인수급 #코스닥 중)
- **장중**: 제목+날짜 / 핵심 수치 / 원인–결과 / 관점 하나(P/C 추이 해석 우선) / 해시태그 10개 / 마지막 줄 "데이터: 한국투자증권 Open API"

## 7. 전달 (필수, 발행보다 먼저)

`SendUserFile`(status `proactive`)로 **표지 PNG + 한눈에 보기(`*_all.jpg`) + zip**을 보낸다. 같은 메시지에 캡션 전문을 복붙 가능한 코드 블록으로 출력한다. 늦어도 반드시 보낸다.

## 8. 발행 (세 덱 모두)

포기하는 유일한 사유는 업로드 실패다.
```bash
bash cards/publish.sh cards/out/<deck>_<YYYYMMDD> cards/out/content_<deck>.json
```
- 마지막 줄이 `ALL_OK`일 때만 발행한다. `URL_CHECK_FAILED`면 한 번 더 실행하고, 그래도 실패하면 "자동 발행 실패, 수동으로 올려라"라고 알린다.
- `mcp__Metricool_Social_Media_Management__createScheduledPost`: blogId `"6885044"`. `TZ=Asia/Seoul date +%H:%M` 확인 후 발행 시각(미장 08:00, 장중 13:30, 국장 16:30) 전이면 오늘 그 시각 정각, 지났으면 지금부터 5분 뒤. info:
  `{"autoPublish": true, "draft": false, "descendants": [], "firstCommentText": "", "hasNotReadNotes": false, "media": [URL 카드 순서대로], "mediaAltText": [카드 수만큼, 키워드 포함], "providers": [{"network": "instagram"}], "publicationDate": {"dateTime": "YYYY-MM-DDTHH:MM:00", "timezone": "Asia/Seoul"}, "shortener": false, "smartLinkData": {"ids": []}, "text": 캡션 그대로, "instagramData": {"type": "POST", "collaborators": [], "showReelOnFeed": true, "isAiGenerated": false}}`
- 응답에서 providers status가 `PENDING`이고 media가 `static.metricool.com` 주소로 바뀌었는지 확인한다. 실패하면 오류 원문을 그대로 알린다.

## 9. 마지막 메시지

한국어 반말 두세 줄: (1) 발행 성공 여부와 예약 시각(또는 "수동으로 올려라"), (2) 오늘 한 줄 요약, (3) 데이터 수집 실패나 못 구해서 뺀 항목.
