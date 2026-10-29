#!/usr/bin/env bash
# 완성된 카드 PNG를 공개 저장소에 올리고, Metricool에 넣을 공개 URL을 출력한다.
#   bash cards/publish.sh cards/out/us_20261029 [content.json]
# 이미지 저장소: /home/user/winwin-cards (공개 저장소 baseball2000212-coder/winwin-cards)가 있으면 거기에,
# 없으면 kis-data 작업 브랜치의 cards/posts/ 에 올린다(kis-data가 공개일 때만 통함).
# 주소는 커밋 SHA로 고정한 raw.githubusercontent.com 주소를 쓴다.
# 캡션·content.json은 kis-data 쪽 cards/posts/ 에만 남긴다(공개 저장소에는 이미지만).
set -e
DIR=${1%/}
NAME=$(basename "$DIR")
HERE=$(cd "$(dirname "$0")/.." && pwd)
PUB=/home/user/winwin-cards

push() {  # $1=저장소 경로 $2=브랜치
  for i in 0 2 4 8 16; do
    sleep $i
    git -C "$1" push -q origin "HEAD:$2" && return 0
  done
  return 1
}

# 기록용 사본(캡션·content)은 항상 kis-data 작업 브랜치에
REC="$HERE/cards/posts/$NAME"
mkdir -p "$REC"
[ -f "$DIR/caption.txt" ] && cp "$DIR/caption.txt" "$REC"/
[ -n "$2" ] && cp "$2" "$REC/content.json"

if [ -d "$PUB/.git" ]; then
  REPO=baseball2000212-coder/winwin-cards
  ROOT=$PUB; BRANCH=$(git -C "$PUB" rev-parse --abbrev-ref HEAD); DEST=posts/$NAME
  git -C "$PUB" pull -q --rebase origin "$BRANCH" || true
else
  REPO=baseball2000212-coder/kis-data
  ROOT=$HERE; BRANCH=$(git -C "$HERE" rev-parse --abbrev-ref HEAD); DEST=cards/posts/$NAME
fi
mkdir -p "$ROOT/$DEST"
cp "$DIR"/*_[0-9].png "$ROOT/$DEST"/ 2>/dev/null || true
cp "$DIR"/*_[0-9][0-9].png "$ROOT/$DEST"/ 2>/dev/null || true

git -C "$HERE" add "$REC"
[ "$ROOT" = "$HERE" ] && git -C "$HERE" add "$DEST"
git -C "$HERE" diff --staged --quiet || git -C "$HERE" commit -q -m "cards $NAME"
push "$HERE" "$(git -C "$HERE" rev-parse --abbrev-ref HEAD)"
if [ "$ROOT" != "$HERE" ]; then
  git -C "$ROOT" add "$DEST"
  git -C "$ROOT" diff --staged --quiet || git -C "$ROOT" commit -q -m "cards $NAME"
  push "$ROOT" "$BRANCH"
fi

SHA=$(git -C "$ROOT" rev-parse HEAD)
ok=1
for f in $(cd "$ROOT" && ls "$DEST"/*.png | sort -V); do
  url="https://raw.githubusercontent.com/$REPO/$SHA/$f"
  code=$(curl -s -o /dev/null -w "%{http_code} %{content_type}" "$url")
  echo "$url  [$code]"
  case "$code" in 200\ image/png*) ;; *) ok=0 ;; esac
done
[ $ok = 1 ] && echo "ALL_OK" || { echo "URL_CHECK_FAILED"; exit 1; }
