#!/usr/bin/env bash
# 카드 렌더링 환경 준비. 컨테이너가 새로 뜰 때마다 실행해도 된다(이미 있으면 건너뜀).
set -e
python3 -c "import matplotlib, PIL" 2>/dev/null || pip install -q matplotlib pillow 2>&1 | grep -v WARNING || true
mkdir -p ~/.fonts
# 제목은 Noto Sans KR Black(900), 나머지는 Noto Sans KR (사용자 지정 10/29)
N=https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/KR
for w in Regular Medium Bold Black; do
  [ -s ~/.fonts/NotoSansKR-$w.otf ] || curl -sSL -o ~/.fonts/NotoSansKR-$w.otf "$N/NotoSansKR-$w.otf"
done
fc-cache -f >/dev/null
fc-list : style | grep -q "Black" && fc-list : family | grep -q "Noto Sans KR" && echo "setup ok"
