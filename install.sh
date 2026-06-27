#!/usr/bin/env bash
# =============================================================================
# AI Berkshire — Claude Code 安装脚本 (macOS / Linux)
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
REPO_URL="https://github.com/xbtlin/ai-berkshire.git"
INSTALL_DIR="${AI_BERKSHIRE_HOME:-$HOME/ai-berkshire}"
COMMANDS_DIR="$HOME/.claude/commands"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

USE_COPY=false
UNINSTALL=false
SKIP_DEPS=false

# ---------------------------------------------------------------------------
# 帮助信息
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
AI Berkshire — Claude Code 价值投资研究 Skill 合集安装器

用法: bash install.sh [选项]

选项:
  --copy         使用文件拷贝而非符号链接（不支持符号链接的环境）
  --uninstall    卸载所有已安装的 skills 并删除仓库
  --skip-deps    跳过 Python 依赖安装
  --help         显示此帮助信息

环境变量:
  AI_BERKSHIRE_HOME    安装目录（默认: \$HOME/ai-berkshire）
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
for arg in "$@"; do
    case "$arg" in
        --copy)    USE_COPY=true ;;
        --uninstall) UNINSTALL=true ;;
        --skip-deps) SKIP_DEPS=true ;;
        --help)    usage ;;
        *)         echo "未知参数: $arg"; usage ;;
    esac
done

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   AI Berkshire — Claude Code 投资研究 Skill 安装器${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════${NC}"
echo ""

# ---------------------------------------------------------------------------
# 卸载逻辑
# ---------------------------------------------------------------------------
if $UNINSTALL; then
    echo -e "${YELLOW}[卸载]${NC} 清理已安装的 skills..."

    if [ -d "$COMMANDS_DIR" ]; then
        removed=0
        for md in "$COMMANDS_DIR"/*.md; do
            if [ -L "$md" ]; then
                target=$(readlink "$md")
                if echo "$target" | grep -q "ai-berkshire"; then
                    rm -f "$md"
                    echo "  移除: $(basename "$md")"
                    ((removed++))
                fi
            elif [ -f "$md" ]; then
                if head -5 "$md" 2>/dev/null | grep -qi "ai.berkshire\|巴菲特.*芒格.*段永平\|投资研究.*四大师"; then
                    rm -f "$md"
                    echo "  移除: $(basename "$md")"
                    ((removed++))
                fi
            fi
        done
        echo "  共移除 $removed 个技能文件"
    fi

    if [ -d "$INSTALL_DIR" ]; then
        echo ""
        echo -e "${YELLOW}[卸载]${NC} 仓库目录保留在: $INSTALL_DIR"
        echo "  如需删除请手动执行: rm -rf $INSTALL_DIR"
    fi

    echo ""
    echo -e "${GREEN}✅ 卸载完成${NC}"
    echo ""
    exit 0
fi

# ---------------------------------------------------------------------------
# 前置条件检查
# ---------------------------------------------------------------------------
echo -e "${CYAN}[1/5]${NC} 检查前置条件..."

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo -e "  ${RED}✗${NC} $1 未安装"
        return 1
    else
        local ver
        ver=$("$1" --version 2>&1 | head -1 || echo "OK")
        echo -e "  ${GREEN}✓${NC} $1 — $ver"
    fi
}

FAIL=0
check_cmd git   || FAIL=1
check_cmd python3 || { check_cmd python || FAIL=1; }

if [ $FAIL -ne 0 ]; then
    echo ""
    echo -e "${RED}请先安装缺失的前置条件，然后重新运行本脚本。${NC}"
    exit 1
fi

PYTHON=$(command -v python3 2>/dev/null || command -v python)

echo ""

# ---------------------------------------------------------------------------
# Clone / 更新仓库
# ---------------------------------------------------------------------------
echo -e "${CYAN}[2/5]${NC} 准备仓库..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  仓库已存在，执行 git pull 更新..."
    cd "$INSTALL_DIR"
    git pull --ff-only origin main 2>&1 | sed 's/^/  /' || echo -e "  ${YELLOW}⚠${NC} git pull 失败，继续使用当前版本"
    cd - >/dev/null
else
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "  ${YELLOW}⚠${NC} 目录已存在但非 git 仓库，跳过 clone"
    else
        echo "  git clone → $INSTALL_DIR"
        git clone "$REPO_URL" "$INSTALL_DIR" 2>&1 | sed 's/^/  /'
    fi
fi

echo ""

# ---------------------------------------------------------------------------
# 安装 Skills 到 ~/.claude/commands/
# ---------------------------------------------------------------------------
echo -e "${CYAN}[3/5]${NC} 安装 Skills → $COMMANDS_DIR"

mkdir -p "$COMMANDS_DIR"

SKILLS_DIR="$INSTALL_DIR/skills"
if [ ! -d "$SKILLS_DIR" ]; then
    echo -e "  ${RED}✗${NC} 找不到 skills/ 目录: $SKILLS_DIR"
    exit 1
fi

installed=0
for src in "$SKILLS_DIR"/*.md; do
    name=$(basename "$src")
    dest="$COMMANDS_DIR/$name"

    # 清理旧的链接或文件
    [ -L "$dest" ] && rm -f "$dest"
    [ -f "$dest" ] && rm -f "$dest"

    if $USE_COPY; then
        cp "$src" "$dest"
        echo "  已复制: $name"
    else
        ln -sf "$src" "$dest"
        echo "  已链接: $name"
    fi
    ((installed++))
done

echo "  共安装 $installed 个技能"

echo ""

# ---------------------------------------------------------------------------
# Python 依赖
# ---------------------------------------------------------------------------
echo -e "${CYAN}[4/5]${NC} Python 工具依赖..."

if $SKIP_DEPS; then
    echo "  已跳过"
else
    echo "  核心工具 (financial_rigor, report_audit 等) 使用 Python 标准库，零额外依赖。"

    if [ -f "$INSTALL_DIR/tools/xueqiu_scraper.py" ]; then
        if "$PYTHON" -c "import playwright" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} playwright 已安装（xueqiu_scraper.py 需要）"
        else
            echo -e "  ${YELLOW}ℹ${NC} playwright 未安装（仅 xueqiu_scraper.py 需要，非核心功能）"
            echo "  如需使用雪球爬虫，请执行: pip install playwright && playwright install chromium"
        fi
    fi
fi

echo ""

# ---------------------------------------------------------------------------
# 完成
# ---------------------------------------------------------------------------
echo -e "${CYAN}[5/5]${NC} 安装完成！"
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ AI Berkshire 已就绪${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo ""
echo "  安装目录: $INSTALL_DIR"
echo "  技能目录: $COMMANDS_DIR"
echo "  已安装:   $installed 个投资研究技能"
echo ""
echo -e "  ${CYAN}快速开始:${NC}"
echo "    /investment-research 腾讯        # 深度研究一家公司"
echo "    /investment-team 美团             # 四大师并行研究"
echo "    /investment-checklist 茅台, 腾讯  # 多公司六关筛选"
echo "    /industry-funnel AI算力           # 行业漏斗精选"
echo "    /earnings-review 腾讯 2025Q4      # 财报一手资料精读"
echo "    /portfolio-review                # 组合仓位管理"
echo ""
echo -e "  ${CYAN}更新:${NC}"
if $USE_COPY; then
echo "    cd $INSTALL_DIR && git pull && bash install.sh --copy"
else
echo "    cd $INSTALL_DIR && git pull        # 符号链接模式，自动生效"
fi
echo ""
