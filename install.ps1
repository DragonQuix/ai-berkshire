<#
.SYNOPSIS
    AI Berkshire — Claude Code 安装脚本 (Windows PowerShell)
.DESCRIPTION
    将 AI Berkshire 投资研究 Skill 合集安装到 Claude Code。
.PARAMETER Uninstall
    卸载所有已安装的 skills
.PARAMETER SkipDeps
    跳过 Python 依赖安装
.PARAMETER InstallDir
    自定义安装目录（默认: $HOME/ai-berkshire）
.EXAMPLE
    pwsh install.ps1
    pwsh install.ps1 -Uninstall
#>
param(
    [switch]$Uninstall = $false,
    [switch]$SkipDeps = $false,
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
$RepoURL = "https://github.com/xbtlin/ai-berkshire.git"
if (-not $InstallDir) {
    $InstallDir = Join-Path $HOME "ai-berkshire"
}
$CommandsDir = Join-Path $HOME ".claude\commands"

# ---------------------------------------------------------------------------
# 帮助函数
# ---------------------------------------------------------------------------
function Write-Banner {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "   AI Berkshire — Claude Code 投资研究 Skill 安装器" -ForegroundColor Cyan
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([int]$Step, [int]$Total, [string]$Text)
    Write-Host "[$Step/$Total] " -NoNewline -ForegroundColor Cyan
    Write-Host $Text
}

function Test-Command {
    param([string]$Cmd)
    $found = Get-Command $Cmd -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "  $(Get-CheckMark $true) $Cmd" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  $(Get-CheckMark $false) $Cmd 未安装" -ForegroundColor Red
        return $false
    }
}

function Get-CheckMark {
    param([bool]$ok)
    if ($ok) { return "✓" } else { return "✗" }
}

# ---------------------------------------------------------------------------
# 卸载
# ---------------------------------------------------------------------------
if ($Uninstall) {
    Write-Banner
    Write-Host "[卸载] 清理已安装的 skills..." -ForegroundColor Yellow
    Write-Host ""

    if (Test-Path $CommandsDir) {
        $removed = 0
        Get-ChildItem "$CommandsDir\*.md" | ForEach-Object {
            $content = Get-Content $_.FullName -TotalCount 5 -ErrorAction SilentlyContinue
            if ($content -match "AI Berkshire|投资研究|巴菲特|四大师") {
                Remove-Item $_.FullName -Force
                Write-Host "  移除: $($_.Name)"
                $removed++
            }
        }
        Write-Host "  共移除 $removed 个技能文件"
    }

    if (Test-Path $InstallDir) {
        Write-Host ""
        Write-Host "[卸载] 仓库目录保留在: $InstallDir" -ForegroundColor Yellow
        Write-Host "  如需删除请手动执行: Remove-Item -Recurse -Force '$InstallDir'"
    }

    Write-Host ""
    Write-Host "卸载完成" -ForegroundColor Green
    Write-Host ""
    exit 0
}

# ---------------------------------------------------------------------------
# 安装开始
# ---------------------------------------------------------------------------
Write-Banner

# ---- 前置条件 ----
Write-Step 1 5 "检查前置条件..."

$allOk = $true
if (-not (Test-Command git))    { $allOk = $false }
if (-not (Test-Command python)) { $allOk = $false }

if (-not $allOk) {
    Write-Host ""
    Write-Host "请先安装缺失的前置条件，然后重新运行本脚本。" -ForegroundColor Red
    exit 1
}

$pythonCmd = (Get-Command python).Source
Write-Host ""

# ---- Clone / 更新 ----
Write-Step 2 5 "准备仓库..."

if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Host "  仓库已存在，执行 git pull 更新..."
    Push-Location $InstallDir
    try {
        git pull --ff-only origin main 2>&1 | ForEach-Object { Write-Host "  $_" }
    } catch {
        Write-Host "  ⚠ git pull 失败，继续使用当前版本" -ForegroundColor Yellow
    }
    Pop-Location
} else {
    if (Test-Path $InstallDir) {
        Write-Host "  ⚠ 目录已存在但非 git 仓库，跳过 clone" -ForegroundColor Yellow
    } else {
        Write-Host "  git clone → $InstallDir"
        git clone $RepoURL $InstallDir 2>&1 | ForEach-Object { Write-Host "  $_" }
    }
}

Write-Host ""

# ---- 安装 Skills ----
Write-Step 3 5 "安装 Skills → $CommandsDir"

if (-not (Test-Path $CommandsDir)) {
    New-Item -ItemType Directory -Path $CommandsDir -Force | Out-Null
}

$skillsDir = Join-Path $InstallDir "skills"
if (-not (Test-Path $skillsDir)) {
    Write-Host "  ✗ 找不到 skills/ 目录: $skillsDir" -ForegroundColor Red
    exit 1
}

$installed = 0
Get-ChildItem "$skillsDir\*.md" | ForEach-Object {
    $dest = Join-Path $CommandsDir $_.Name

    # 清理旧文件
    if (Test-Path $dest) {
        Remove-Item $dest -Force
    }

    Copy-Item $_.FullName $dest -Force
    Write-Host "  已复制: $($_.Name)"
    $installed++
}

Write-Host "  共安装 $installed 个技能"

Write-Host ""

# ---- Python 依赖 ----
Write-Step 4 5 "Python 工具依赖..."

if ($SkipDeps) {
    Write-Host "  已跳过"
} else {
    Write-Host "  核心工具 (financial_rigor, report_audit 等) 使用 Python 标准库，零额外依赖。"

    $xueqiuScraper = Join-Path $InstallDir "tools\xueqiu_scraper.py"
    if (Test-Path $xueqiuScraper) {
        $hasPlaywright = & $pythonCmd -c "import playwright" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ playwright 已安装（xueqiu_scraper.py 需要）" -ForegroundColor Green
        } else {
            Write-Host "  ℹ playwright 未安装（仅 xueqiu_scraper.py 需要，非核心功能）" -ForegroundColor Yellow
            Write-Host "  如需使用雪球爬虫，请执行: pip install playwright && playwright install chromium"
        }
    }
}

Write-Host ""

# ---- 完成 ----
Write-Step 5 5 "安装完成！"
Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ AI Berkshire 已就绪" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  安装目录: $InstallDir"
Write-Host "  技能目录: $CommandsDir"
Write-Host "  已安装:   $installed 个投资研究技能"
Write-Host ""
Write-Host "  快速开始:" -ForegroundColor Cyan
Write-Host "    /investment-research 腾讯        # 深度研究一家公司"
Write-Host "    /investment-team 美团             # 四大师并行研究"
Write-Host "    /investment-checklist 茅台, 腾讯  # 多公司六关筛选"
Write-Host "    /industry-funnel AI算力           # 行业漏斗精选"
Write-Host "    /earnings-review 腾讯 2025Q4      # 财报一手资料精读"
Write-Host "    /portfolio-review                # 组合仓位管理"
Write-Host ""
Write-Host "  更新:" -ForegroundColor Cyan
Write-Host "    cd $InstallDir; git pull; pwsh install.ps1        # Windows 拷贝模式，需重新运行"
Write-Host ""
