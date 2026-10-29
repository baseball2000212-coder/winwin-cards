# -*- coding: utf-8 -*-
"""winwin_macro 카드뉴스 키트 — 데이터 계산, 차트, HTML 카드, 렌더링.

  python3 cards/kit.py fetch us|kr          최신 JSON 받기 → cards/out/data_us.json
  python3 cards/kit.py facts us|kr          카드에 쓸 수치를 계산해서 출력
  python3 cards/kit.py build content.json   content.json(그날 문구) → PNG 덱

수치는 전부 KIS JSON에서 계산한다. content.json에는 문구와 리서치 수치(금리·연준 확률·일정)만 쓴다.
디자인 규칙은 cards/RUNBOOK.md 참고.
"""
import os, sys, json, glob, html, re, subprocess, zipfile, datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
KST = dt.timezone(dt.timedelta(hours=9))
WD = "월화수목금토일"

C = dict(ink="#222222", body="#45515E", gray="#8E8E93", faint="#A9AEB8", blue="#1456F0",
         navy="#17437D", lblue="#EFF4FF", panel="#F5F7FA", line="#ECEEF2", row="#F0F2F5",
         red="#E5383B", orange="#E8590C", pink="#FDF2FA", magenta="#C2389E",
         lred="#F4A3A5", sky="#60A5FA")

NAMES = {"005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션", "086520": "에코프로",
         "005380": "현대차", "000270": "기아", "012450": "한화에어로스페이스", "064350": "현대로템",
         "329180": "HD현대중공업", "011200": "HMM", "034020": "두산에너빌리티", "052690": "한전기술"}
SECTOR_ORDER = ["반도체", "이차전지", "자동차", "방산", "조선해운", "원전"]
SECTOR_LABEL = {"조선해운": "조선·해운"}

DECKS = {  # prefix, 상단 줄 이름, 데이터 종류
    "us": dict(prefix="us", kind="미장 마감", data="us"),
    "kr_close": dict(prefix="kr", kind="국장 마감", data="kr"),
    "kr_live": dict(prefix="live", kind="장중 파생", data="kr"),
    "earn": dict(prefix="earn", kind="어닝 분석", data="us"),  # 기업 실적 분석(비정기)
}


# ───────────────────────── 데이터 ─────────────────────────
def now_kst():
    return dt.datetime.now(KST)


def wd(yyyymmdd):
    d = dt.datetime.strptime(yyyymmdd, "%Y%m%d")
    return WD[d.weekday()]


def md_label(yyyymmdd):
    d = dt.datetime.strptime(yyyymmdd, "%Y%m%d")
    return f"{d.month}월 {d.day}일 ({WD[d.weekday()]})"


def curl(url, dst):
    subprocess.run(["curl", "-sSfL", "-o", dst, f"{url}?{int(now_kst().timestamp())}"], check=True)
    return dst


def git_data(path, dst, ref="origin/main"):
    """저장소 파일을 git으로 받는다(비공개 저장소에서도 동작). 실패하면 공개 raw 주소로 받는다."""
    repo = os.path.dirname(ROOT)
    try:
        if ref == "origin/main":
            subprocess.run(["git", "-C", repo, "fetch", "-q", "origin", "main"], check=True, timeout=60)
        out = subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"], check=True, capture_output=True,
                             timeout=60).stdout
        open(dst, "wb").write(out)
    except Exception:  # 저장소가 공개일 때만 통한다
        commit = "main" if ref == "origin/main" else ref
        curl(f"https://raw.githubusercontent.com/baseball2000212-coder/kis-data/{commit}/{path}", dst)
    return dst


def fetch(kind, sha=None):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, f"data_{kind}.json")
    git_data(f"data/{kind}/latest.json", dst, sha or "origin/main")
    return json.load(open(dst, encoding="utf-8"))


def load(kind):
    p = os.path.join(OUT, f"data_{kind}.json")
    if not os.path.exists(p):
        return fetch(kind)
    return json.load(open(p, encoding="utf-8"))


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def series(data, name):
    """(시각 HHMMSS 리스트, 종가 리스트, 고가 리스트, 저가 리스트, 전일 종가) — 차트 선은 종가를 잇는다."""
    if name in ("NDX", "SPX", "COMP", "VIX"):
        d = data["indices"][name]
        b = d["bars"]
        return ([r["stck_cntg_hour"] for r in b], [f(r["optn_prpr"]) for r in b],
                [f(r["optn_hgpr"]) for r in b], [f(r["optn_lwpr"]) for r in b],
                f(d["summary"].get("ovrs_nmix_prdy_clpr")))
    if name in ("QQQ", "SPY", "NVDA"):
        b = data["stocks"][name]["bars"]
        return ([r["xhms"] for r in b], [f(r["last"]) for r in b],
                [f(r["high"]) for r in b], [f(r["low"]) for r in b], None)
    if name in ("KOSPI", "KOSDAQ"):
        d = data["index_코스피" if name == "KOSPI" else "index_코스닥"]
        tk = d.get("time_key", "stck_cntg_hour")
        b = [r for r in d["bars"] if "090000" <= r[tk] <= "153000"]
        return ([r[tk] for r in b], [f(r["bstp_nmix_prpr"]) for r in b],
                [f(r["bstp_nmix_hgpr"]) for r in b], [f(r["bstp_nmix_lwpr"]) for r in b],
                f(d["summary"].get("prdy_nmix")))
    if name == "FUT":
        b = [r for r in data["future_chart"]["bars"] if "090000" <= r["stck_cntg_hour"] <= "154500"]
        o1 = data["future_price"]["output1"]
        prev = f(o1.get("futs_sdpr")) or f(data["future_chart"]["summary"].get("futs_prdy_clpr"))
        return ([r["stck_cntg_hour"] for r in b], [f(r["futs_prpr"]) for r in b],
                [f(r["futs_hgpr"]) for r in b], [f(r["futs_lwpr"]) for r in b], prev)
    raise KeyError(name)


def path_facts(data, name):
    t, c, h, l, prev = series(data, name)
    hi_i = max(range(len(h)), key=lambda i: h[i])
    lo_i = min(range(len(l)), key=lambda i: l[i])
    out = dict(n=len(c), first=t[0], last=t[-1],
               high=h[hi_i], high_time=t[hi_i], low=l[lo_i], low_time=t[lo_i], close=c[-1], prev=prev)
    if prev:
        out["chg"] = round(c[-1] - prev, 2)
        out["pct"] = round((c[-1] / prev - 1) * 100, 2)
    return out


def hm(t):
    return f"{t[:2]}:{t[2:4]}"


def comma(v, nd=2):
    return f"{v:,.{nd}f}"


def pct(v, nd=2):
    return f"{v:+.{nd}f}%"


def eok(v):
    return f"{v:+,.0f}억"


def facts_us(data):
    out = {"asof_kst": data["asof_kst"], "errors": data.get("errors")}
    any_bar = data["indices"]["NDX"]["bars"][-1]
    sd = any_bar["stck_bsop_date"]
    out["session_date"] = f"{sd} ({wd(sd)})"
    for k in ("NDX", "SPX", "COMP", "VIX"):
        p = path_facts(data, k)
        s = data["indices"][k]["summary"]
        p.update(open=f(s.get("ovrs_prod_oprc")), day_high=f(s.get("ovrs_prod_hgpr")),
                 day_low=f(s.get("ovrs_prod_lwpr")), close_api=f(s.get("ovrs_nmix_prpr")),
                 pct_api=f(s.get("prdy_ctrt")))
        out[k] = p
    for k in ("QQQ", "SPY", "NVDA"):
        t, c, h, l, _ = series(data, k)
        p = path_facts(data, k)
        o = f(data["stocks"][k]["bars"][0]["open"])
        p.update(open=o, from_open_pct=round((c[-1] / o - 1) * 100, 2))
        out[k] = p
    return out


def facts_kr(data):
    out = {"asof_kst": data["asof_kst"], "errors": data.get("errors"),
           "option_source": data.get("option_source"),
           "center_src": (data.get("option_meta") or {}).get("center_src"),
           "future_name": data.get("future_name"), "future_is_mini": data.get("future_is_mini"),
           "option_expiry": data.get("option_expiry")}
    for k in ("KOSPI", "KOSDAQ", "FUT"):
        try:
            out[k] = path_facts(data, k)
        except Exception as e:
            out[k] = f"실패: {e}"
    out["flow_eok"] = data.get("flow_check_eok")
    out["program_eok"] = data.get("program_check_eok")
    out["derivatives"] = data.get("derivatives")
    sec = data.get("sectors") or {}
    out["sectors"] = {k: sec[k]["avg_pct"] for k in SECTOR_ORDER if k in sec}
    out["stocks_close_pct"] = {NAMES.get(c, c): v.get("chg_pct") for c, v in (data.get("stocks") or {}).items()}
    fx = data.get("fx") or {}
    out["fx_ref_only"] = {k: ({kk: v.get(kk) for kk in ("close", "chg", "chg_pct", "date")} if isinstance(v, dict) else v)
                          for k, v in fx.items()}
    inv = data.get("investor_daily") or []
    if inv:
        r0 = inv[0]
        e = lambda k: round(f(r0.get(k)) / 100) if f(r0.get(k)) is not None else None
        out["investor_detail_eok"] = dict(date=r0.get("stck_bsop_date"), 외국인=e("frgn_ntby_tr_pbmn"),
                                          개인=e("prsn_ntby_tr_pbmn"), 기관=e("orgn_ntby_tr_pbmn"),
                                          연기금=e("fund_ntby_tr_pbmn"), 투신=e("ivtr_ntby_tr_pbmn"),
                                          금융투자=e("scrt_ntby_tr_pbmn"))
        # 외국인 연속 매수/매도
        sign0 = (f(r0.get("frgn_ntby_tr_pbmn")) or 0) > 0
        n, tot = 0, 0.0
        for r in inv:
            v = f(r.get("frgn_ntby_tr_pbmn")) or 0
            if (v > 0) != sign0 or v == 0:
                break
            n += 1
            tot += v
        out["foreign_streak"] = dict(direction="순매수" if sign0 else "순매도", days=n, total_eok=round(tot / 100))
    return out


def pc_trend(today, n=5):
    """직전 영업일 파일 + 오늘 latest → P/C 추이. chain·실시간 조건을 못 맞춘 날은 뺀다."""
    pts, rows = [], []
    base = (today.get("asof_kst") or now_kst().isoformat())[:10].replace("-", "")
    cur = dt.datetime.strptime(base, "%Y%m%d").date()
    tries = 0
    while len(rows) < n - 1 and tries < 12:
        cur -= dt.timedelta(days=1)
        tries += 1
        if cur.weekday() >= 5:
            continue
        ymd = cur.strftime("%Y%m%d")
        dst = os.path.join(OUT, f"kr_{ymd}.json")
        try:
            if not os.path.exists(dst):
                git_data(f"data/kr/{ymd}.json", dst)
            rows.append((ymd, json.load(open(dst, encoding="utf-8"))))
        except Exception:
            continue
    rows = list(reversed(rows)) + [(base, today)]
    for ymd, d in rows:
        if d.get("option_source") != "chain" or (d.get("option_meta") or {}).get("center_src") != "실시간":
            continue
        dv = d.get("derivatives") or {}
        try:
            kpct = f(d["index_코스피"]["summary"]["bstp_nmix_prdy_ctrt"])
        except Exception:
            kpct = None
        pts.append(dict(date=ymd, pc=dv.get("put_call_oi_ratio"), call=dv["call"]["oi_total"],
                        put=dv["put"]["oi_total"], kospi_pct=kpct, expiry=d.get("option_expiry"),
                        n=dv["call"].get("n"), asof=d.get("asof_kst")))
    return pts


# ───────────────────────── 차트 ─────────────────────────
def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt
    for p in glob.glob(os.path.expanduser("~/.fonts/*")):
        try:
            font_manager.fontManager.addfont(p)
        except Exception:
            pass
    plt.rcParams.update({"font.family": "Noto Sans KR", "axes.unicode_minus": False,
                         "savefig.transparent": True})
    return plt


S = 2  # 차트는 CSS 크기의 2배로 그린다


def fs(css_px):  # CSS px → matplotlib pt (dpi 200, 2배)
    return css_px * S * 72 / 200


def lw(css_px):
    return css_px * S * 72 / 200


def _fig(w, h):
    plt = _mpl()
    fig = plt.figure(figsize=(w * S / 200, h * S / 200), dpi=200)
    ax = fig.add_axes([0.01, 0.10, 0.98, 0.88])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_yticks([])
    ax.tick_params(length=0, colors=C["faint"], labelsize=fs(17))
    return plt, fig, ax


BAL = dict(boxstyle="round,pad=0.38", fc=C["lblue"], ec=C["blue"], lw=lw(2.2))
ARR = dict(arrowstyle="-|>,head_width=0.4,head_length=0.85", color=C["blue"], lw=lw(3.0), shrinkB=7)


def _dot(ax, x, y, color, size=13):
    ax.plot([x], [y], "o", ms=fs(size), color=color, mec="white", mew=lw(3), zorder=5)


def path_chart(dst, t, ys, prev=None, hi_text=None, lo_text=None, ticks=None, w=852, h=430,
               mini=False, now_text=None, hi_i=None, lo_i=None, fill=True, prev_label="전일 종가"):
    plt, fig, ax = _fig(w, h)
    n = len(ys)
    x = list(range(n))
    up = ys[-1] >= (prev if prev else ys[0])
    col = C["red"] if up else C["blue"]
    vals = ys + ([prev] if prev else [])
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    if mini:
        ax.set_position([0.0, 0.02, 1.0, 0.96])
        ymin, ymax = lo - span * 0.15, hi + span * 0.15
    else:
        # 말풍선이 잘리지 않게 위·아래 여백을 px로 확보한다
        ax.set_position([0.01, 52 / h, 0.98, 1 - 52 / h - 0.01])
        ax_h = h - 52
        dy = 44 if h >= 420 else 18  # 차트가 낮으면 말풍선을 점에 더 붙인다
        top_px = dy + (hi_text.count("\n") + 1) * 31 + 30 if hi_text else 40
        bot_px = dy + (lo_text.count("\n") + 1) * 31 + 30 if lo_text else 24
        data_px = max(ax_h - top_px - bot_px, 80)
        k = span / data_px
        ymin, ymax = lo - bot_px * k, hi + top_px * k
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-n * 0.02, (n - 1) * 1.02 + 1)
    ax.plot(x, ys, color=col, lw=lw(4.2 if not mini else 3.6), solid_capstyle="round", zorder=3)
    if fill:
        ax.fill_between(x, ys, ymin, color=col, alpha=0.08, lw=0, zorder=1)
    if prev:
        ax.axhline(prev, color=C["gray"], ls=(0, (5, 4)), lw=lw(2.2), zorder=2)
        if not mini:
            right = abs(ys[-1] - prev) < abs(ys[0] - prev)  # 선과 덜 겹치는 쪽에 라벨
            ax.text(n - 1 if right else 0, prev, prev_label, color=C["gray"], fontsize=fs(17), va="bottom",
                    ha="right" if right else "left", fontweight="bold",
                    bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none", alpha=0.85))
    if not mini:
        hi_i = hi_i if hi_i is not None else max(x, key=lambda i: ys[i])
        lo_i = lo_i if lo_i is not None else min(x, key=lambda i: ys[i])
        for i in {hi_i, lo_i, n - 1}:
            _dot(ax, i, ys[i], col)
        def bal(i, text, above):
            left_side = i > n * 0.55
            dx = -60 if left_side else 60
            dy = (44 if h >= 420 else 18) * (1 if above else -1)
            ax.annotate(text, xy=(i, ys[i]), xytext=(fs(dx), fs(dy)), textcoords="offset points",
                        ha="right" if left_side else "left", va="bottom" if above else "top",
                        fontsize=fs(21), fontweight="bold", color=C["blue"], bbox=BAL,
                        arrowprops=ARR, annotation_clip=False, zorder=6, linespacing=1.35)
        if hi_text:
            bal(hi_i, hi_text, True)
        if lo_text:
            bal(lo_i, lo_text, False)
        if now_text:
            ax.annotate(now_text, xy=(n - 1, ys[-1]), xytext=(fs(-14), fs(-30 if up else 30)),
                        textcoords="offset points", ha="right", va="top" if up else "bottom",
                        fontsize=fs(19), fontweight="bold", color=C["orange"], zorder=6)
        if ticks:
            idx, lab = [], []
            for tt in ticks:
                cands = [i for i in x if t[i][:4] >= tt.replace(":", "")]
                if cands and cands[0] not in idx:
                    idx.append(cands[0])
                    lab.append(tt)
            ax.set_xticks(idx)
            ax.set_xticklabels(lab)
        else:
            ax.set_xticks([])
    else:
        _dot(ax, n - 1, ys[-1], col, 11)
        ax.set_xticks([])
    fig.savefig(dst, transparent=True)
    plt.close(fig)
    return dst


def bars_v(dst, cats, vals, unit="억", w=852, h=470, fmt=None, plain=False, scale=1.0):
    """세로 막대. plain=True면 등락이 아닌 크기(매출·투자) 막대: 부호 없이, 과거는 네이비·마지막은 파랑."""
    plt, fig, ax = _fig(w, h)
    ax.set_position([0.02, 0.14, 0.96, 0.80])
    if plain:
        cols = [C["navy"]] * (len(vals) - 1) + [C["blue"]]
        fmt = fmt or (lambda v: f"{v:,.0f}{unit}")
    else:
        cols = [C["red"] if v > 0 else C["blue"] for v in vals]
    x = range(len(vals))
    ax.bar(x, vals, color=cols, width=0.56, zorder=3)
    ax.axhline(0, color=C["line"], lw=lw(2))
    m = max(abs(v) for v in vals) or 1
    ax.set_ylim(min(0, min(vals)) - m * 0.22, max(0, max(vals)) + m * 0.22)
    for i, v in enumerate(vals):
        lab = fmt(v) if fmt else f"{v:+,.0f}{unit}"
        ax.text(i, v + (m * 0.03 if v >= 0 else -m * 0.03), lab, ha="center",
                va="bottom" if v >= 0 else "top", color=cols[i], fontsize=fs(30 * scale), fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats, fontsize=fs(26 * scale), color=C["ink"], fontweight="bold")
    ax.tick_params(axis="x", pad=fs(14))
    fig.savefig(dst, transparent=True)
    plt.close(fig)
    return dst


def bars_h(dst, cats, vals, w=852, h=760, unit="%"):
    """가로 막대. 큰 값이 위. 종목명은 막대 반대편, 값은 막대 끝."""
    plt, fig, ax = _fig(w, h)
    ax.set_position([0.0, 0.0, 1.0, 1.0])
    pairs = sorted(zip(cats, vals), key=lambda p: p[1])
    m = max(abs(v) for _, v in pairs) or 1
    lo = min(0, min(v for _, v in pairs))
    hi = max(0, max(v for _, v in pairs))
    pad = m * 0.55
    ax.set_xlim(lo - pad, hi + pad)
    for i, (c, v) in enumerate(pairs):
        col = C["red"] if v > 0 else C["blue"]
        ax.barh(i, v, color=col, height=0.62, zorder=3)
        ax.text(-m * 0.03 if v >= 0 else m * 0.03, i, c, ha="right" if v >= 0 else "left", va="center",
                fontsize=fs(23), color=C["ink"], fontweight="bold")
        ax.text(v + (m * 0.03 if v >= 0 else -m * 0.03), i, f"{v:+.2f}{unit}", ha="left" if v >= 0 else "right",
                va="center", fontsize=fs(23), color=col, fontweight="bold")
    ax.axvline(0, color=C["line"], lw=lw(2))
    ax.set_ylim(-0.7, len(pairs) - 0.3)
    ax.set_xticks([])
    fig.savefig(dst, transparent=True)
    plt.close(fig)
    return dst


def lines_chart(dst, labels, series_, ref=None, w=852, h=470, ylim=None, label_right=True):
    """점 연결 차트. series_ = [{name, vals, color, texts(각 점 라벨)}]. ref = {value, label}."""
    plt, fig, ax = _fig(w, h)
    ax.set_position([0.04, 0.12, 0.84 if label_right else 0.92, 0.80])
    x = list(range(len(labels)))
    allv = [v for s in series_ for v in s["vals"] if v is not None] + ([ref["value"]] if ref else [])
    lo, hi = min(allv), max(allv)
    span = (hi - lo) or 1
    ax.set_ylim(*(ylim or (lo - span * 0.35, hi + span * 0.45)))
    ax.set_xlim(-0.35, len(labels) - 0.65)
    if ref:
        ax.axhline(ref["value"], color=C["gray"], ls=(0, (5, 4)), lw=lw(2.2), zorder=1)
        ax.text(-0.3, ref["value"], ref["label"], color=C["gray"], fontsize=fs(18),
                va="bottom", ha="left", fontweight="bold")
    for s in series_:
        col = s.get("color", C["blue"])
        xs = [i for i, v in zip(x, s["vals"]) if v is not None]
        vs = [v for v in s["vals"] if v is not None]
        ax.plot(xs, vs, color=col, lw=lw(4), zorder=3)
        for j, (i, v) in enumerate(zip(xs, vs)):
            _dot(ax, i, v, col)
            txt = (s.get("texts") or [None] * len(vs))[j]
            if txt:
                below = s.get("below", False)
                ax.annotate(txt, xy=(i, v), xytext=(0, fs(-22 if below else 20)), textcoords="offset points",
                            ha="center", va="top" if below else "bottom", fontsize=fs(s.get("size", 21)),
                            color=col, fontweight="bold", linespacing=1.2)
        if label_right and s.get("name"):
            ax.text(xs[-1] + 0.22, vs[-1], s["name"], color=col, fontsize=fs(21), fontweight="bold",
                    va="center", ha="left", clip_on=False)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=fs(19), color=C["gray"])
    ax.tick_params(axis="x", pad=fs(10))
    fig.savefig(dst, transparent=True)
    plt.close(fig)
    return dst


def pc_chart(dst, pts, w=852, h=560):
    plt, fig, ax = _fig(w, h)
    ax.set_position([0.02, 0.17, 0.96, 0.78])
    x = list(range(len(pts)))
    calls = [p["call"] for p in pts]
    puts = [p["put"] for p in pts]
    m = max(calls + puts)
    bw = 0.34
    ax.bar([i - bw / 2 for i in x], calls, width=bw, color=C["lred"], zorder=2, label="콜 미결제")
    ax.bar([i + bw / 2 for i in x], puts, width=bw, color=C["sky"], zorder=2, label="풋 미결제")
    ax.set_ylim(0, m * 1.9)
    ax2 = ax.twinx()
    for sp in ax2.spines.values():
        sp.set_visible(False)
    ax2.set_yticks([])
    pcs = [p["pc"] for p in pts]
    lo, hi = min(pcs), max(pcs)
    sp_ = (hi - lo) or 0.2
    ax2.set_ylim(lo - sp_ * 2.4, hi + sp_ * 1.5)  # 범례와 최고점 라벨이 겹치지 않게 위쪽 여유
    ax2.plot(x, pcs, color=C["orange"], lw=lw(4), zorder=4)
    top_i = max(x, key=lambda i: pcs[i])
    for i, v in enumerate(pcs):
        big = i in (top_i, len(pcs) - 1)
        ax2.plot([i], [v], "o", ms=fs(13), color=C["orange"], mec="white", mew=lw(3), zorder=5)
        ax2.annotate(f"{v:.2f}", xy=(i, v), xytext=(0, fs(18)), textcoords="offset points", ha="center",
                     va="bottom", fontsize=fs(28 if big else 21), color=C["orange"], fontweight="bold")
    for i in range(1, len(pts)):
        if pts[i]["expiry"] != pts[i - 1]["expiry"]:
            ax.axvline(i - 0.5, color=C["gray"], ls=(0, (2, 3)), lw=lw(1.8))
            ax.text(i - 0.5, m * 1.02, f" 월물 변경→{pts[i]['expiry'][-2:]}월", color=C["gray"], fontsize=fs(16))
    labs = []
    for i, p in enumerate(pts):
        d = p["date"]
        top = f"{int(d[4:6])}/{int(d[6:])} ({wd(d)})"
        if i == len(pts) - 1 and p.get("asof"):
            bot = p["asof"][11:16]
        else:
            bot = f"{p['kospi_pct']:+.2f}%" if p.get("kospi_pct") is not None else ""
        labs.append(f"{top}\n{bot}")
    ax.set_xticks(x)
    ax.set_xticklabels(labs, fontsize=fs(18), color=C["gray"], linespacing=1.4)
    ax.legend(loc="upper left", frameon=False, fontsize=fs(18), ncol=2, labelcolor=C["body"])
    fig.savefig(dst, transparent=True)
    plt.close(fig)
    return dst


# ───────────────────────── HTML ─────────────────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;background:#FFFFFF}
body{font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif;color:#222222;letter-spacing:-0.3px;word-break:keep-all}
.card{position:relative;width:1080px;height:1350px;padding:84px 84px 132px;display:flex;flex-direction:column;background:#FFFFFF}
.top{display:flex;justify-content:space-between;align-items:center;height:40px}
.top .l{display:flex;align-items:center;gap:16px}
.sec{color:#8E8E93;font-weight:700;font-size:24px;white-space:pre}
.top .r{color:#8E8E93;font-size:22px}
.top .r b{color:#1456F0;font-weight:700}
.top .r .asof{color:#E8590C;font-weight:700}
.badge{display:inline-block;font-size:22px;font-weight:700;border-radius:999px;padding:5px 16px;line-height:1.2}
.b-blue{background:#EFF4FF;color:#1456F0}
.b-pink{background:#FDF2FA;color:#C2389E}
h1{font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif;font-weight:900;font-size:64px;line-height:1.25;letter-spacing:-1.5px;color:#141414;margin-top:40px}
.sub{font-size:29px;color:#45515E;margin-top:16px;line-height:1.4}
.body{flex:1;display:flex;flex-direction:column;gap:26px;margin-top:36px;min-height:0;overflow:hidden}
.box{background:#FFFFFF;border:1.5px solid #ECEEF2;border-radius:24px;box-shadow:0 4px 18px rgba(20,40,90,.06);padding:28px 30px}
.grow{flex:1;min-height:0;display:flex;flex-direction:column}
.grow .chart{flex:1;min-height:0}
.chart{position:relative}
.chart img{position:absolute;left:0;top:0;width:100%;height:100%;display:block}
.fill{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:space-around}
.fill > .bullets{flex:1;justify-content:space-evenly}
.fill .bl{font-size:31px}
.tbl.fill .row{flex:1}
.sx.fill .row{flex:1}
.kv.fill .row{flex:1}
.thead{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:16px;border-bottom:1.5px solid #ECEEF2;margin-bottom:14px}
.thead .tk{font-size:32px;font-weight:700}
.thead .ds{font-size:21px;color:#8E8E93;margin-left:12px}
.thead .v{font-size:34px;font-weight:700}
.up{color:#E5383B}.dn{color:#1456F0}.flat{color:#222222}
.bullets{display:flex;flex-direction:column;gap:18px}
.bl{display:flex;align-items:flex-start;gap:18px;font-size:29px;line-height:1.42;color:#222222}
.bl .n{flex:none;width:32px;height:32px;border-radius:50%;background:#EFF4FF;color:#1456F0;font-weight:700;font-size:19px;display:flex;align-items:center;justify-content:center;margin-top:5px}
.bl b,.navy{color:#17437D;font-weight:700}
.callout{background:#F5F7FA;border-left:9px solid #1456F0;border-radius:0 20px 20px 0;padding:26px 40px 28px 38px}
.callout .lb{font-size:22px;color:#1456F0;font-weight:700;margin-bottom:10px}
.callout .fit{font-size:31px;font-weight:700;color:#222222;white-space:nowrap;overflow:hidden;line-height:1.45}
.callout .fit.minor{font-weight:400;color:#45515E}
.tl{display:flex;flex-direction:column}
.tl .it{display:flex;gap:24px;padding:16px 0;border-top:1.5px solid #F0F2F5}
.tl .it:first-child{border-top:none;padding-top:4px}
.tl .tm{flex:none;width:96px;color:#1456F0;font-weight:700;font-size:27px}
.tl .hd{font-weight:700;font-size:28px;line-height:1.35}
.tl .ds{color:#45515E;font-size:24px;margin-top:4px;line-height:1.4}
.kv .row{display:flex;align-items:center;padding:12px 4px;border-top:1.5px solid #F0F2F5}
.kv .row:first-child{border-top:none}
.kv .k{width:250px;flex:none;font-size:27px;color:#8E8E93;font-weight:700}
.kv .val{flex:none;font-size:40px;font-weight:700;min-width:250px}
.kv .nt{flex:1;text-align:right;font-size:24px;color:#8E8E93}
.tbl .row{display:flex;align-items:center;padding:16px 6px;border-top:1.5px solid #F0F2F5;gap:22px}
.tbl .row:first-child{border-top:none}
.tbl .row.key{background:#EFF4FF;border-radius:14px;border-top-color:transparent}
.tbl .row.key + .row{border-top-color:transparent}
.tbl .w{flex:none;width:230px;font-size:24px;color:#8E8E93;font-weight:700;line-height:1.35}
.tbl .e{flex:1;min-width:0}
.tbl .e .t{font-size:28px;font-weight:700;line-height:1.35}
.tbl .row.key .t,.tbl .row.key .w{color:#17437D}
.tbl .e .d{font-size:23px;color:#45515E;margin-top:3px;line-height:1.35}
.pill{display:inline-block;background:#1456F0;color:#fff;font-size:18px;font-weight:700;border-radius:999px;padding:3px 12px;margin-left:10px;vertical-align:4px}
.foot{position:absolute;left:84px;right:84px;bottom:58px;display:flex;justify-content:space-between;align-items:baseline}
.foot .pg{font-size:22px;color:#8E8E93}
.foot .src{font-size:20px;color:#A9AEB8}
/* 표지 */
.cv h1{font-size:90px;line-height:1.2;letter-spacing:-2px;margin-top:70px}
.cv .idx{font-weight:900;font-size:48px;letter-spacing:-1px;margin-top:26px}
.cv .desc{font-size:29px;color:#45515E;margin-top:14px;line-height:1.4}
.chips{display:flex;gap:14px;margin-top:26px;flex-wrap:nowrap}
.chip{background:#EFF4FF;color:#17437D;font-weight:700;font-size:25px;border-radius:999px;padding:9px 22px;white-space:nowrap}
.hr{height:1.5px;background:#ECEEF2;margin:30px 0 22px}
.meta{color:#1456F0;font-weight:700;font-size:22px}
.tiles{display:flex;gap:14px;margin-top:18px}
.tile{flex:1;background:#FFFFFF;border:1.5px solid #ECEEF2;border-radius:16px;box-shadow:0 4px 18px rgba(20,40,90,.06);padding:16px 18px}
.tile .tl_{font-size:20px;color:#8E8E93;font-weight:700}
.tile .tv{font-size:36px;font-weight:700;margin-top:4px;white-space:nowrap}
.tile .tc{font-size:22px;font-weight:700;margin-top:2px}
.panel{flex:1;min-height:0;background:#F5F7FA;border-radius:24px;margin-top:22px;padding:20px 26px 18px;display:flex;flex-direction:column}
.panel .pl{font-size:20px;color:#8E8E93;font-weight:700;margin-bottom:6px}
/* 섹터 */
.spot{display:flex;align-items:center;gap:30px;padding:22px 30px}
.spot .big{font-size:64px;font-weight:700;line-height:1}
.spot .nm{font-size:24px;color:#8E8E93;font-weight:700;margin-top:10px}
.spot .vl{width:1.5px;align-self:stretch;background:#ECEEF2}
.spot .why{flex:1}
.spot .why .badge{margin-bottom:10px}
.spot .why .t{color:#17437D;font-weight:700;font-size:27px;line-height:1.42}
.sx .row{display:flex;align-items:center;padding:4px 10px;border-top:1.5px solid #F0F2F5;gap:16px}
.sx .row:first-child{border-top:none}
.sx .row.key{background:#EFF4FF;border-radius:14px;border-top-color:transparent}
.sx .row.key + .row{border-top-color:transparent}
.sx .s{flex:none;width:150px;font-size:27px;font-weight:700}
.sx .p{flex:none;width:230px}
.sx .p .pv{font-size:27px;font-weight:700;line-height:1.3}
.sx .p .ld{font-size:18px;color:#8E8E93;white-space:nowrap;line-height:1.3}
.sx .y{flex:1;min-width:0;font-size:24px;color:#45515E;white-space:nowrap;overflow:hidden}
.sx .row.key .s{color:#17437D}
/* 밈 카드: 실제 밈 이미지 대신 이모지 + 글자로 만든 원본 포맷 */
.emo{font-family:'Noto Color Emoji',sans-serif;line-height:1}
.dk{flex:1;display:flex;flex-direction:column;gap:22px}
.dk .row{flex:1;display:flex;align-items:stretch;gap:0;border:1.5px solid #ECEEF2;border-radius:24px;overflow:hidden;box-shadow:0 4px 18px rgba(20,40,90,.06)}
.dk .face{flex:none;width:300px;display:flex;align-items:center;justify-content:center;font-size:150px}
.dk .row.no .face{background:#F5F7FA}
.dk .row.yes .face{background:#EFF4FF}
.dk .txt{flex:1;display:flex;flex-direction:column;justify-content:center;padding:30px 38px;background:#FFFFFF}
.dk .lb{font-size:24px;font-weight:700;margin-bottom:12px}
.dk .row.no .lb{color:#8E8E93}
.dk .row.yes .lb{color:#1456F0}
.dk .t{font-size:40px;font-weight:900;line-height:1.3;letter-spacing:-1px}
.dk .row.no .t{color:#8E8E93;text-decoration:line-through;text-decoration-thickness:3px}
.dk .d{font-size:25px;color:#45515E;margin-top:10px;line-height:1.4}
.vs{flex:1;display:flex;gap:22px}
.vs .col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:24px;padding:30px 24px;text-align:center}
.vs .col.a{background:#F5F7FA}
.vs .col.b{background:#EFF4FF}
.vs .lb{font-size:28px;font-weight:900;color:#8E8E93;letter-spacing:-0.5px}
.vs .col.b .lb{color:#1456F0}
.vs .em{font-size:170px;margin:34px 0 30px}
.vs .t{font-size:44px;font-weight:900;line-height:1.25;letter-spacing:-1px}
.vs .d{font-size:25px;color:#45515E;margin-top:14px;line-height:1.4}
"""


def esc(s):
    s = html.escape(str(s))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def cls(v):
    if v is None:
        return "flat"
    return "up" if v > 0 else ("dn" if v < 0 else "flat")


def page(inner, extra_css=""):
    return f'<meta charset="utf-8"><html><head><meta charset="utf-8"><style>{CSS}{extra_css}</style></head><body>{inner}</body></html>'


BADGES = {"us": ("미국 주식", "b-blue"), "macro": ("매크로", "b-blue"), "spot": ("현물", "b-blue"),
          "deriv": ("선물·파생", "b-pink"), None: None, "none": None}


def topline(ctx, num=None, section="", badge=None):
    left = f'<span class="sec">{num:02d}  {esc(section)}</span>' if num else f'<span class="sec">{esc(section)}</span>'
    b = BADGES.get(badge)
    if b:
        left += f'<span class="badge {b[1]}">{b[0]}</span>'
    asof = f' · <span class="asof">{esc(ctx["asof_label"])}</span>' if ctx.get("asof_label") else ""
    return f'<div class="top"><div class="l">{left}</div><div class="r"><b>{ctx["kind"]}</b> · {ctx["date_label"]}{asof}</div></div>'


def foot(ctx, i):
    return (f'<div class="foot"><span class="pg">{i:02d} / {ctx["total"]:02d}</span>'
            f'<span class="src">{esc(ctx.get("source") or "데이터: 한국투자증권 Open API")}</span></div>')


def h1(lines):
    if isinstance(lines, str):
        lines = [lines]
    return "<h1>" + "<br>".join(esc(x) for x in lines) + "</h1>"


def bullets(items):
    return '<div class="bullets">' + "".join(
        f'<div class="bl"><span class="n">{i + 1}</span><span>{esc(t)}</span></div>' for i, t in enumerate(items)) + "</div>"


def callout(c):
    if not c:
        return ""
    lines = "".join(f'<div class="fit">{esc(x)}</div>' for x in c.get("lines", []))
    lines += "".join(f'<div class="fit minor">{esc(x)}</div>' for x in c.get("minor", []))
    return f'<div class="callout"><div class="lb">{esc(c.get("label", "한 줄"))}</div>{lines}</div>'


def thead(tk, ds, val=None, v=None):
    right = f'<span class="v {cls(v)}">{esc(val)}</span>' if val else ""
    return f'<div class="thead"><div><span class="tk">{esc(tk)}</span><span class="ds">{esc(ds)}</span></div>{right}</div>'


def slot(ctx, name, fn, style=""):
    """차트 자리. 1차 렌더에서 크기를 재고, 그 크기로 fn(dst, w, h)를 그린 뒤 2차 렌더한다."""
    dst = os.path.join(ctx["dir"], name)
    ctx["jobs"][name] = lambda w, h: fn(dst, w, h)
    img = f'<img src="{name}">' if ctx.get("pass") == 2 else ""
    return f'<div class="chart" data-src="{name}" style="{style}">{img}</div>'


def chart_box(chart, head="", foot_txt="", grow=True):
    return f'<div class="box{" grow" if grow else ""}">{head}{chart}{foot_txt}</div>'


def timeline(items):
    return '<div class="box tl">' + "".join(
        f'<div class="it"><div class="tm">{esc(x["time"])}</div><div><div class="hd">{esc(x["head"])}</div>'
        f'<div class="ds">{esc(x.get("desc", ""))}</div></div></div>' for x in items) + "</div>"


def keyvals(rows):
    out = '<div class="box kv">'
    for r in rows:
        out += (f'<div class="row"><div class="k">{esc(r["label"])}</div>'
                f'<div class="val {cls(r.get("dir"))}">{esc(r["value"])}</div>'
                f'<div class="nt">{esc(r.get("note", ""))}</div></div>')
    return out + "</div>"


def table(rows):
    out = '<div class="box tbl">'
    for r in rows:
        pill = '<span class="pill">핵심</span>' if r.get("key") else ""
        out += (f'<div class="row{" key" if r.get("key") else ""}"><div class="w">{esc(r["when"])}</div>'
                f'<div class="e"><div class="t">{esc(r["event"])}{pill}</div>'
                + (f'<div class="d">{esc(r["desc"])}</div>' if r.get("desc") else "") + "</div></div>")
    return out + "</div>"


# ───────────────────────── 카드 종류 ─────────────────────────
US_TICKS = ["09:30", "11:00", "13:00", "15:00", "16:00"]
KR_TICKS = ["09:00", "11:00", "13:00", "15:00", "15:30"]
SERIES_DESC = {"NDX": "나스닥100 지수 · 5분봉 09:30–16:00 ET", "QQQ": "나스닥100 ETF · 1분봉 09:30–16:00 ET",
               "SPX": "S&P 500 지수 · 5분봉 09:30–16:00 ET", "SPY": "S&P 500 ETF · 1분봉 09:30–16:00 ET",
               "NVDA": "엔비디아 · 1분봉 09:30–16:00 ET", "KOSPI": "코스피 지수 · 5분봉",
               "KOSDAQ": "코스닥 지수 · 5분봉", "FUT": "코스피200 선물 · 1분봉"}
SERIES_TK = {"NDX": "NDX", "QQQ": "QQQ", "SPX": "SPX", "SPY": "SPY", "NVDA": "NVDA", "KOSPI": "코스피",
             "KOSDAQ": "코스닥", "FUT": "K200 선물"}


def _path_slot(ctx, card, i, mini=False, style=""):
    """경로 차트 자리 + (마지막 값, 전일 대비 %)."""
    name = card["series"]
    t, ys, hs, ls, prev = series(ctx["data"], name)
    if card.get("until"):
        keep = [j for j, tt in enumerate(t) if tt[:4] <= card["until"].replace(":", "")]
        t, ys, hs, ls = [t[j] for j in keep], [ys[j] for j in keep], [hs[j] for j in keep], [ls[j] for j in keep]
    hi_i = max(range(len(hs)), key=lambda j: hs[j])
    lo_i = min(range(len(ls)), key=lambda j: ls[j])
    us = name in ("NDX", "QQQ", "SPX", "SPY", "NVDA")
    ticks = card.get("ticks") or (US_TICKS if us else KR_TICKS)
    if not us and t and t[-1][:4] < "1530":
        mins = lambda x: int(x[:2]) * 60 + int(x[-2:])
        last = hm(t[-1])
        ticks = [x for x in ticks if mins(x) <= mins(last) - 45] + [last]  # 마지막 시각과 붙는 눈금은 뺀다
    pv = prev if card.get("prev", True) else None
    if not mini:  # 고점·저점 봉은 종가 대신 실제 고가·저가를 찍어 선의 꼭짓점이 말풍선 수치와 맞게 한다
        ys = list(ys)
        ys[hi_i], ys[lo_i] = hs[hi_i], ls[lo_i]
    fn = lambda dst, w, h: path_chart(dst, t, ys, prev=pv, hi_text=card.get("hi_text"), lo_text=card.get("lo_text"),
                                      ticks=ticks, w=w, h=h, mini=mini, now_text=card.get("now_text"),
                                      hi_i=hi_i, lo_i=lo_i, prev_label="전일 정산가" if name == "FUT" else "전일 종가")
    chg = (ys[-1] / prev - 1) * 100 if prev else None
    return slot(ctx, f"c{i}_{'mini' if mini else 'path'}.png", fn, style), ys[-1], chg


def card_cover(ctx, c, i):
    idx = c.get("index_line") or {}
    tiles = "".join(
        f'<div class="tile"><div class="tl_">{esc(t["label"])}</div><div class="tv">{esc(t["value"])}</div>'
        f'<div class="tc {cls(t.get("dir"))}">{esc(t.get("chg", ""))}</div></div>' for t in c["tiles"])
    chips = "".join(f'<span class="chip">{esc(x)}</span>' for x in c.get("chips", []))
    mini = ""
    if c.get("mini") and c["mini"].get("bars"):  # 표지 패널에 크기 막대(매출 추이 등)
        mb = c["mini"]["bars"]
        sl = slot(ctx, f"c{i}_minibars.png", lambda dst, w, h: bars_v(
            dst, mb["cats"], mb["vals"], unit=mb.get("unit", ""), w=w, h=h, plain=True, scale=0.75),
            style="flex:1;min-height:0")
        mini = f'<div class="panel"><div class="pl">{esc(c["mini"]["label"])}</div>{sl}</div>'
    elif c.get("mini"):
        sl, _, _ = _path_slot(ctx, {"series": c["mini"]["series"], "until": c["mini"].get("until")}, i, mini=True,
                              style="flex:1;min-height:0")
        mini = f'<div class="panel"><div class="pl">{esc(c["mini"]["label"])}</div>{sl}</div>'
    return (f'<div class="card cv">{topline(ctx, None, c.get("section", "데일리 리포트"))}{h1(c["title"])}'
            f'<div class="idx {cls(idx.get("dir"))}">{esc(idx.get("text", ""))}</div>'
            f'<div class="desc">{esc(c.get("desc", ""))}</div><div class="chips">{chips}</div><div class="hr"></div>'
            f'<div class="meta">{esc(c.get("meta", ""))}</div><div class="tiles">{tiles}</div>{mini}{foot(ctx, i)}</div>')


def _frame(ctx, c, i, body):
    return (f'<div class="card">{topline(ctx, i, c.get("section", ""), c.get("badge"))}{h1(c["title"])}'
            + (f'<div class="sub">{esc(c["sub"])}</div>' if c.get("sub") else "")
            + f'<div class="body">{body}</div>{foot(ctx, i)}</div>')


def _extras(c):
    out = ""
    if c.get("timeline"):
        out += timeline(c["timeline"])
    if c.get("keyvals"):
        out += keyvals(c["keyvals"])
    if c.get("bullets"):
        out += bullets(c["bullets"])
    return out + callout(c.get("callout"))


def _head(c):
    hd = c.get("header")
    return thead(hd["ticker"], hd.get("desc", ""), hd.get("value"), hd.get("dir")) if hd else ""


def card_path(ctx, c, i):
    sl, last, chg = _path_slot(ctx, c, i)
    hd = c.get("header") or {}
    val = hd.get("value") or (f"{chg:+.2f}%" if chg is not None else "")
    head = thead(hd.get("ticker", SERIES_TK[c["series"]]), hd.get("desc", SERIES_DESC[c["series"]]), val,
                 hd.get("dir", chg))
    return _frame(ctx, c, i, chart_box(sl, head) + _extras(c))


def card_bars(ctx, c, i):
    d = ctx["data"]
    if c.get("source") == "investors":
        fl = d["flow_check_eok"]
        cats, vals = ["개인", "외국인", "기관"], [fl["개인"], fl["외국인"], fl["기관"]]
    elif c.get("source") == "program":
        pg = d["program_check_eok"]
        cats, vals = ["차익", "비차익", "전체"], [pg["차익"], pg["비차익"], pg["전체"]]
    else:
        cats, vals = c["cats"], c["vals"]
    if c.get("override"):
        vals = c["override"]
    sl = slot(ctx, f"c{i}_bars.png", lambda dst, w, h: bars_v(dst, cats, vals, unit=c.get("unit", "억"), w=w, h=h,
                                                             plain=c.get("plain", False)))
    return _frame(ctx, c, i, chart_box(sl, _head(c)) + _extras(c))


def card_hbars(ctx, c, i):
    d = ctx["data"]
    if c.get("source") == "stocks12":
        cats, vals = [], []
        for code, v in d["stocks"].items():
            if v.get("chg_pct") is not None:
                cats.append(NAMES.get(code, code))
                vals.append(v["chg_pct"])
    else:
        cats, vals = c["cats"], c["vals"]
    sl = slot(ctx, f"c{i}_hbars.png", lambda dst, w, h: bars_h(dst, cats, vals, w=w, h=h))
    return _frame(ctx, c, i, chart_box(sl, _head(c)) + _extras(c))


def card_lines(ctx, c, i):
    ser = []
    for s in c["series"]:
        s = dict(s)
        s["color"] = {"blue": C["blue"], "navy": C["navy"], "red": C["red"], "orange": C["orange"],
                      "gray": C["gray"]}.get(s.get("color"), s.get("color", C["blue"]))
        ser.append(s)
    sl = slot(ctx, f"c{i}_lines.png", lambda dst, w, h: lines_chart(
        dst, c["labels"], ser, ref=c.get("ref"), w=w, h=h, ylim=c.get("ylim"), label_right=c.get("label_right", True)))
    return _frame(ctx, c, i, chart_box(sl, _head(c)) + _extras(c))


def card_keyvals(ctx, c, i):
    body = ""
    if c.get("chart"):
        cc = dict(c["chart"])
        sl, last, chg = _path_slot(ctx, cc, i)
        hd = cc.get("header") or {}
        body += chart_box(sl, thead(hd.get("ticker", SERIES_TK[cc["series"]]), hd.get("desc", SERIES_DESC[cc["series"]]),
                                    hd.get("value", f"{chg:+.2f}%" if chg is not None else ""), hd.get("dir", chg)))
    body += keyvals(c["rows"]).replace('class="box kv"', 'class="box kv fill"' if not c.get("chart") else 'class="box kv"')
    c = {k: v for k, v in c.items() if k != "keyvals"}
    return _frame(ctx, c, i, body + _extras(c))


def card_table(ctx, c, i):
    return _frame(ctx, c, i, table(c["rows"]).replace('class="box tbl"', 'class="box tbl fill"') + _extras(c))


def card_points(ctx, c, i):
    body = keyvals(c["keyvals"]) if c.get("keyvals") else ""
    if c.get("bullets"):
        body += f'<div class="box fill">{bullets(c["bullets"])}</div>'
    return _frame(ctx, c, i, body + callout(c.get("callout")))


def card_sector(ctx, c, i):
    d = ctx["data"]
    sec = d["sectors"]
    sp = c["spotlight"]
    spv = sec[sp["sector"]]["avg_pct"]
    spot = (f'<div class="box spot"><div><div class="big {cls(spv)}">{spv:+.1f}%</div>'
            f'<div class="nm">{esc(SECTOR_LABEL.get(sp["sector"], sp["sector"]))} · 대장주 평균</div></div><div class="vl"></div>'
            f'<div class="why"><span class="badge b-blue">왜</span><div class="t">{"<br>".join(esc(x) for x in sp["why"])}</div></div></div>')
    rows = ""
    for k in SECTOR_ORDER:
        if k not in sec:
            continue
        s = sec[k]
        key = k == sp["sector"]
        reason = "(위 참조)" if key else c.get("reasons", {}).get(k, "")
        n1 = " · 1종목 기준" if s.get("n") == 1 else ""
        rows += (f'<div class="row{" key" if key else ""}"><div class="s">{esc(SECTOR_LABEL.get(k, k))}</div>'
                 f'<div class="p"><div class="pv {cls(s["avg_pct"])}">{s["avg_pct"]:+.1f}%</div>'
                 f'<div class="ld">{esc("·".join(s["leaders"]))}{n1}</div></div>'
                 f'<div class="y nowrap-cell">{esc(reason)}</div></div>')
    return _frame(ctx, c, i, spot + f'<div class="box sx fill">{rows}</div>' + callout(c.get("callout")))


def card_pc(ctx, c, i):
    pts = ctx.setdefault("_pc", None) or pc_trend(ctx["data"])
    ctx["_pc"] = pts
    if len(pts) < 3:
        return None
    sl = slot(ctx, f"c{i}_pc.png", lambda dst, w, h: pc_chart(dst, pts, w=w, h=h))
    head = thead("P/C 미결제 비율", c.get("header_desc", "풋 미결제 ÷ 콜 미결제 · 최근 영업일"))
    return _frame(ctx, c, i, chart_box(sl, head) + _extras(c))


def card_meme(ctx, c, i):
    """밈 카드. format "drake": rows[{emoji, label, text, desc, no}] — no=True 줄은 회색·취소선.
    format "vs": cols[{label, emoji, text, desc}] 2칸(왼쪽 기대, 오른쪽 현실)."""
    if c.get("format", "drake") == "vs":
        body = '<div class="vs">' + "".join(
            f'<div class="col {"ab"[k]}"><div class="lb">{esc(x["label"])}</div><div class="em emo">{x["emoji"]}</div>'
            f'<div class="t {cls(x.get("dir")) if x.get("dir") is not None else ""}">{esc(x["text"])}</div>'
            + (f'<div class="d">{esc(x["desc"])}</div>' if x.get("desc") else "") + "</div>"
            for k, x in enumerate(c["cols"][:2])) + "</div>"
    else:
        body = '<div class="dk">' + "".join(
            f'<div class="row {"no" if x.get("no") else "yes"}"><div class="face emo">{x["emoji"]}</div>'
            f'<div class="txt"><div class="lb">{esc(x["label"])}</div><div class="t">{esc(x["text"])}</div>'
            + (f'<div class="d">{esc(x["desc"])}</div>' if x.get("desc") else "") + "</div></div>"
            for x in c["rows"]) + "</div>"
    return _frame(ctx, c, i, body + callout(c.get("callout")))


TYPES = dict(cover=card_cover, path=card_path, bars=card_bars, hbars=card_hbars, lines=card_lines,
             keyvals=card_keyvals, table=card_table, points=card_points, sector=card_sector, pc=card_pc,
             meme=card_meme)


# ───────────────────────── 빌드 ─────────────────────────
def build(content_path):
    content = json.load(open(content_path, encoding="utf-8"))
    deck = DECKS[content["deck"]]
    today = content.get("date") or now_kst().strftime("%Y%m%d")
    # 같은 날 같은 덱을 여러 개 만들 때(어닝 분석 등)는 content의 "slug"로 폴더를 나눈다
    ddir = os.path.join(OUT, f"{content['deck']}_{today}" + (f"_{content['slug']}" if content.get("slug") else ""))
    os.makedirs(ddir, exist_ok=True)
    for old in glob.glob(os.path.join(ddir, "*")):
        os.remove(old)
    data = load(deck["data"])
    cards = [c for c in content["cards"] if not c.get("skip")]
    ctx = dict(data=data, dir=ddir, kind=deck["kind"], date_label=md_label(today),
               asof_label=content.get("asof_label"), total=len(cards), jobs={}, source=content.get("source"))

    def write(pass_no):
        ctx["pass"], ctx["jobs"] = pass_no, {}
        out = []
        for i, c in enumerate(cards, 1):
            inner = TYPES[c["type"]](ctx, c, i)
            if inner is None:
                print(f"카드 {i} ({c['type']}) 생략: 데이터 부족 — content에서 빼고 다시 빌드할 것")
                continue
            p = os.path.join(ddir, f"{deck['prefix']}_{today}_{i}.html")
            open(p, "w", encoding="utf-8").write(page(inner))
            out.append(p)
        return out

    htmls = write(1)
    r = subprocess.run(["node", os.path.join(ROOT, "render.js"), "--measure"] + htmls, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2000:]); sys.exit(1)
    sizes = json.loads(r.stdout.strip().splitlines()[-1])
    htmls = write(2)
    for name, job in ctx["jobs"].items():
        w, h = sizes.get(name, (852, 430))
        job(max(w, 200), max(h, 120))
    r = subprocess.run(["node", os.path.join(ROOT, "render.js")] + htmls, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        print(r.stderr[-2000:])
        sys.exit(1)
    pngs = [h.replace(".html", ".png") for h in htmls]
    sheet = contact_sheet(pngs, os.path.join(ddir, f"{deck['prefix']}_{today}_all.jpg"))
    z = os.path.join(ddir, f"{deck['prefix']}_{today}.zip")
    with zipfile.ZipFile(z, "w") as zf:
        for p in pngs:
            zf.write(p, os.path.basename(p))
    if content.get("caption"):
        open(os.path.join(ddir, "caption.txt"), "w", encoding="utf-8").write(content["caption"].strip() + "\n")
    print("cards:", " ".join(os.path.relpath(p, os.path.dirname(ROOT)) for p in pngs))
    print("sheet:", os.path.relpath(sheet, os.path.dirname(ROOT)), " zip:", os.path.relpath(z, os.path.dirname(ROOT)))
    return pngs


def contact_sheet(pngs, dst, cols=4):
    from PIL import Image
    w, h = 360, 450
    rows = (len(pngs) + cols - 1) // cols
    gap = 16
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), "#E9ECF1")
    for k, p in enumerate(pngs):
        im = Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS)
        sheet.paste(im, (gap + (k % cols) * (w + gap), gap + (k // cols) * (h + gap)))
    sheet.save(dst, quality=88)
    return dst


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "fetch":
        d = fetch(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        print("asof_kst", d.get("asof_kst"), "errors", d.get("errors"))
    elif cmd == "facts":
        kind = sys.argv[2]
        d = load(kind)
        print(json.dumps(facts_us(d) if kind == "us" else facts_kr(d), ensure_ascii=False, indent=1))
    elif cmd == "pc":
        print(json.dumps(pc_trend(load("kr")), ensure_ascii=False, indent=1))
    elif cmd == "build":
        build(sys.argv[2])
