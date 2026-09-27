#!/usr/bin/env bash
# Install the Xiaohongshu GEO Agent skills for Claude Code or Codex, then open
# Chrome at the browser extension that matches that client.
#
#   bash install.sh --client claude     # Claude Code  -> Claude in Chrome
#   bash install.sh --client codex      # Codex        -> ChatGPT for Chrome
#   bash install.sh --client claude --no-browser   # skip opening Chrome
#
# Nothing is installed into Chrome silently: the script only opens the Chrome
# Web Store page; the user clicks "Add to Chrome" and signs in themselves.
set -euo pipefail

CLIENT=""
OPEN_BROWSER=1
while [ $# -gt 0 ]; do
  case "$1" in
    --client) CLIENT="${2:-}"; shift 2 ;;
    --no-browser) OPEN_BROWSER=0; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

case "$CLIENT" in
  claude)
    SKILL_DIR="$HOME/.claude/skills"
    EXT_ID="fcoeoabgfenejglbffodgkkbkcdhcgfn"
    EXT_NAME="Claude in Chrome"
    ;;
  codex)
    SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
    EXT_ID="hehggadaopoacecdllhhajmbjkdcmajg"
    EXT_NAME="ChatGPT for Chrome"
    ;;
  *) echo "请用 --client claude 或 --client codex 指明当前使用的 AI 客户端。" >&2; exit 2 ;;
esac

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STORE_URL="https://chromewebstore.google.com/detail/$EXT_ID"

echo "== 1/4 检查环境"
command -v python3 >/dev/null || { echo "缺少 python3（需要 3.9 及以上）。" >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "python3 版本过低，需要 3.9 及以上。" >&2; exit 1; }
for d in xiaohongshu-geo-question-bank xiaohongshu-geo-evaluator xiaohongshu-geo-workbench; do
  [ -d "$REPO_DIR/$d" ] || { echo "安装包不完整，缺少 $d。" >&2; exit 1; }
done
echo "python3 $(python3 -c 'import platform; print(platform.python_version())') · 安装目录 $REPO_DIR"

echo "== 2/4 安装 Skill 到 $SKILL_DIR"
mkdir -p "$SKILL_DIR"
for skill in xiaohongshu-geo-question-bank xiaohongshu-geo-evaluator; do
  target="$SKILL_DIR/$skill"
  if [ -L "$target" ] || [ ! -e "$target" ]; then
    ln -sfn "$REPO_DIR/$skill" "$target"
    echo "已链接 $skill"
  else
    echo "跳过 $skill：$target 已存在且不是本工具创建的链接，请手动处理。" >&2
  fi
done

echo "== 3/4 自检"
( cd "$REPO_DIR/xiaohongshu-geo-question-bank" && python3 tools/local_run.py --help >/dev/null ) \
  && echo "工具可以运行" || { echo "工具自检失败。" >&2; exit 1; }

echo "== 4/4 Chrome 扩展：$EXT_NAME"
case "$(uname -s)" in
  Darwin) CHROME_PROFILE_ROOT="$HOME/Library/Application Support/Google/Chrome" ;;
  Linux)  CHROME_PROFILE_ROOT="$HOME/.config/google-chrome" ;;
  *)      CHROME_PROFILE_ROOT="" ;;
esac
installed=0
if [ -n "$CHROME_PROFILE_ROOT" ] && ls -d "$CHROME_PROFILE_ROOT"/*/Extensions/"$EXT_ID" >/dev/null 2>&1; then
  installed=1
fi
if [ "$installed" = 1 ]; then
  echo "EXTENSION_STATUS=installed"
  echo "$EXT_NAME 已经装在 Chrome 里。"
else
  echo "EXTENSION_STATUS=missing"
  echo "需要安装 $EXT_NAME：$STORE_URL"
fi

if [ "$OPEN_BROWSER" = 1 ]; then
  urls=()
  [ "$installed" = 1 ] || urls+=("$STORE_URL")
  urls+=("https://www.xiaohongshu.com/explore")
  case "$(uname -s)" in
    Darwin)
      if [ -d "/Applications/Google Chrome.app" ] || [ -d "$HOME/Applications/Google Chrome.app" ]; then
        open -a "Google Chrome" "${urls[@]}"
        echo "已在 Chrome 中打开：${urls[*]}"
      else
        echo "没有找到 Google Chrome，请先安装：https://www.google.com/chrome/" >&2
      fi ;;
    Linux)
      if command -v google-chrome >/dev/null; then google-chrome "${urls[@]}" >/dev/null 2>&1 &
      else echo "没有找到 google-chrome，请手动打开：${urls[*]}" >&2; fi ;;
    *) echo "请手动在 Chrome 中打开：${urls[*]}" ;;
  esac
fi

echo
echo "INSTALL_OK client=$CLIENT skills=$SKILL_DIR"
echo "接下来请在 Chrome 里：1) 点「添加至 Chrome」装好 $EXT_NAME 并登录；2) 在小红书页面登录你自己的账号。"
echo "完成后重启 $([ "$CLIENT" = claude ] && echo 'Claude Code' || echo 'Codex')，新 Skill 才会加载。"
