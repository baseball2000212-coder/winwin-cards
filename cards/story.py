# -*- coding: utf-8 -*-
"""인스타 스토리(1080×1920) 한 장. 자동 발행 스토리는 캡션이 안 붙으므로 멘트는 이미지 안에 넣는다.

  python3 cards/story.py story.json   → cards/out/story_<slug>/story_<slug>.png

story.json: {slug, kicker, title[줄], left{label, emoji, text, dir}, right{...}, comment[줄], cta, source}
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import CSS, esc, cls, OUT, ROOT

STORY_CSS = """
html,body{height:1920px}
.card.story{height:1920px;padding:150px 84px 160px;background:#FFFFFF;display:flex;flex-direction:column}
.story .kick{display:inline-block;align-self:flex-start;background:#EFF4FF;color:#1456F0;font-weight:700;font-size:30px;border-radius:999px;padding:8px 24px}
.story h1{font-size:96px;line-height:1.18;letter-spacing:-2.5px;margin-top:40px}
.story .pair{display:flex;gap:24px;margin-top:100px}
.story .side{flex:1;border-radius:32px;padding:44px 20px 40px;text-align:center}
.story .side.a{background:#F5F7FA}
.story .side.b{background:#EFF4FF}
.story .side .lb{font-size:30px;font-weight:900;color:#8E8E93}
.story .side.b .lb{color:#1456F0}
.story .side .em{font-size:220px;margin:40px 0 30px}
.story .side .t{font-size:50px;font-weight:900;letter-spacing:-1px}
.story .arrow{font-size:60px;color:#A9AEB8;align-self:center;font-weight:900}
.story .bubble{position:relative;margin-top:110px;background:#1456F0;color:#FFFFFF;border-radius:40px;padding:44px 50px;font-size:44px;font-weight:700;line-height:1.45;letter-spacing:-0.8px}
.story .bubble:after{content:"";position:absolute;left:90px;top:-34px;border:18px solid transparent;border-bottom:18px solid #1456F0;border-width:0 22px 36px 22px}
.story .cta{margin-top:auto;font-size:36px;font-weight:700;color:#17437D;text-align:center}
.story .src{margin-top:22px;font-size:24px;color:#A9AEB8;text-align:center}
"""


def build(path):
    s = json.load(open(path, encoding="utf-8"))
    d = os.path.join(OUT, f"story_{s['slug']}")
    os.makedirs(d, exist_ok=True)
    side = lambda x, k: (f'<div class="side {k}"><div class="lb">{esc(x["label"])}</div>'
                         f'<div class="em emo">{x["emoji"]}</div><div class="t {cls(x.get("dir"))}">{esc(x["text"])}</div></div>')
    inner = (f'<div class="card story"><span class="kick">{esc(s["kicker"])}</span>'
             f'<h1>{"<br>".join(esc(x) for x in s["title"])}</h1>'
             f'<div class="pair">{side(s["left"], "a")}<div class="arrow">→</div>{side(s["right"], "b")}</div>'
             f'<div class="bubble">{"<br>".join(esc(x) for x in s["comment"])}</div>'
             f'<div class="cta">{esc(s.get("cta", ""))}</div><div class="src">{esc(s.get("source", ""))}</div></div>')
    html = os.path.join(d, f"story_{s['slug']}.html")
    open(html, "w", encoding="utf-8").write(
        f'<meta charset="utf-8"><html><head><meta charset="utf-8"><style>{CSS}{STORY_CSS}</style></head>'
        f'<body data-h="1920">{inner}</body></html>')
    r = subprocess.run(["node", os.path.join(ROOT, "render.js"), html], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr[-1500:])
    print("story:", os.path.relpath(html.replace(".html", ".png"), os.path.dirname(ROOT)))


if __name__ == "__main__":
    build(sys.argv[1])
