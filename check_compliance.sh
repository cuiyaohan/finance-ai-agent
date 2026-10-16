#!/usr/bin/env bash
# 发布前合规自检（一键）
# 用法：cd agent-demos && bash check_compliance.sh
# 退出码：0 = 全部通过；1 = 有命中项
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR" || exit 1

WORDS_RAW="_shared/high_risk_words.txt"
WORDS_CLEAN="$(mktemp -t hrw)"
# 关键：必须去掉注释行与空行，否则 grep -F -f 里的空模式会匹配所有行（假阳性）
grep -v '^#' "$WORDS_RAW" | grep -v '^[[:space:]]*$' > "$WORDS_CLEAN"
trap 'rm -f "$WORDS_CLEAN"' EXIT

FAILED=0
GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; NC=$'\033[0m'

echo "================ 合规自检 ================"
echo "项目根目录：$ROOT_DIR"
echo

# ---------- 1) 高危词扫描 ----------
# 用 Python 扫描器而非 grep -F -f：BSD grep 在多模式文件下对多字节 UTF-8
# 存在边界效应，会把 `git clone ...` 误判为命中（已实测复现）。
echo "[1/4] 高危词扫描（$(grep -c . "$WORDS_CLEAN") 个词，Python 精确匹配）"
SCAN_DIRS=""
for d in v0-invest-intel/output v0-report-automation/output v1-invest-intel/output docs; do
  [ -d "$d" ] && SCAN_DIRS="$SCAN_DIRS $d"
done
[ -f "README.md" ] && SCAN_DIRS="$SCAN_DIRS README.md"
[ -f ".env.example" ] && SCAN_DIRS="$SCAN_DIRS .env.example"
if [ -z "$SCAN_DIRS" ]; then
  echo "  ${YELLOW}⚠ 没有可扫描的输出目录（还没跑过 Demo？）${NC}"
else
  HITS=$(python3 scan_high_risk.py --words "$WORDS_RAW" --scan $SCAN_DIRS 2>&1)
  if [ $? -ne 0 ]; then
    echo "$HITS" | while IFS= read -r line; do echo "  ${RED}命中${NC} $line"; done
    FAILED=1
  else
    echo "  ${GREEN}✅ $HITS${NC}"
  fi
fi
echo

# ---------- 2) 免责声明检查 ----------
echo "[2/4] 免责声明检查"
DISC_FIRST_LINE=$(head -1 _shared/disclaimer.txt)
MISSING=0
while IFS= read -r f; do
  if ! tail -c 1200 "$f" | grep -qF "$DISC_FIRST_LINE"; then
    echo "  ${RED}缺失${NC} $f"
    MISSING=1
  fi
done < <(find v0-invest-intel/output v0-report-automation/output -type f -name "*.md" 2>/dev/null)
if [ "$MISSING" -eq 0 ]; then
  echo "  ${GREEN}✅ 所有输出文件末尾均含免责声明${NC}"
else
  FAILED=1
fi
echo

# ---------- 3) .env 是否被 git 忽略 ----------
echo "[3/4] .env 是否被 Git 忽略"
if [ -f .env ]; then
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git check-ignore -q .env; then
      echo "  ${GREEN}✅ .env 已被 .gitignore 忽略${NC}"
    else
      echo "  ${RED}❌ .env 未被忽略，会被提交！立刻执行：git rm --cached .env${NC}"
      FAILED=1
    fi
  else
    echo "  ${YELLOW}⚠ 当前不是 git 仓库，跳过${NC}"
  fi
else
  echo "  ${YELLOW}⚠ 不存在 .env，跳过${NC}"
fi
for f in v0-invest-intel/.env v0-report-automation/.env v1-invest-intel/.env; do
  if [ -f "$f" ] && ! git check-ignore -q "$f" 2>/dev/null; then
    echo "  ${RED}❌ $f 未被忽略${NC}"
    FAILED=1
  fi
done
echo

# ---------- 4) 邮箱 / 手机号扫描 ----------
echo "[4/4] 邮箱 / 手机号扫描（排除 .venv/.tools/.git/node_modules）"
# 排除代码托管平台地址（git@github.com:… / user@host / …@example.com）：
# 这些是仓库地址不是联系方式，属误报；真实手机号与个人邮箱仍会被命中。
PII=$(grep -rInE "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|1[3-9][0-9]{9}" \
  --include="*.md" --include="*.py" --include="*.txt" --include="*.csv" \
  --exclude-dir=".venv" --exclude-dir=".tools" --exclude-dir=".git" --exclude-dir="node_modules" . 2>/dev/null \
  | grep -v "example.com" | grep -v "@demo" \
  | grep -vE "[A-Za-z0-9._%+-]+@(github|gitlab|bitbucket|gitee)\." )
if [ -n "$PII" ]; then
  echo "$PII" | while IFS= read -r line; do echo "  ${RED}命中${NC} $line"; done
  FAILED=1
else
  echo "  ${GREEN}✅ 未发现邮箱/手机号${NC}"
fi
echo

echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
  echo -e "${GREEN}✅ 合规自检通过${NC}"
  exit 0
else
  echo -e "${RED}❌ 合规自检未通过，请修复上面列出的项后重试${NC}"
  exit 1
fi
