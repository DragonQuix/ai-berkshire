<#
.SYNOPSIS
    AI Berkshire — Claude Code + Codex 安装脚本 (Windows PowerShell)
.DESCRIPTION
    将 AI Berkshire 投资研究 Skill 合集安装到 Claude Code，并安装 Codex 原生 Skill。
.PARAMETER Uninstall
    卸载所有已安装的 skills
.PARAMETER SkipDeps
    跳过 Python 依赖安装
.PARAMETER SkipCodex
    跳过 Codex 原生 Skill 安装
.PARAMETER InstallDir
    自定义安装目录（默认: $HOME/ai-berkshire）
.EXAMPLE
    pwsh install.ps1
    pwsh install.ps1 -Uninstall
#>
param(
    [switch]$Uninstall = $false,
    [switch]$SkipDeps = $false,
    [switch]$SkipCodex = $false,
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
$RepoURL = "https://github.com/xbtlin/ai-berkshire.git"
$ExpectedSkillCount = 19
if (-not $InstallDir) {
    $InstallDir = Join-Path $HOME "ai-berkshire"
}
$CommandsDir = Join-Path $HOME ".claude\commands"
$CodexSkillName = "ai-berkshire"
$CodexHome = $env:CODEX_HOME
if (-not $CodexHome) {
    $CodexHome = [Environment]::GetEnvironmentVariable("CODEX_HOME", "User")
}
if (-not $CodexHome) {
    $CodexHome = Join-Path $HOME ".codex"
}
$CodexSkillsDir = Join-Path $CodexHome "skills"
$CodexSkillDest = Join-Path $CodexSkillsDir $CodexSkillName

# ---------------------------------------------------------------------------
# 帮助函数
# ---------------------------------------------------------------------------
function Write-Banner {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "   AI Berkshire — Claude Code + Codex Skill 安装器" -ForegroundColor Cyan
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

    if (-not $SkipCodex -and (Test-Path $CodexSkillDest)) {
        Remove-Item -LiteralPath $CodexSkillDest -Recurse -Force
        Write-Host "  移除 Codex Skill: $CodexSkillDest"
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
Write-Step 1 6 "检查前置条件..."

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
Write-Step 2 6 "准备仓库..."

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
Write-Step 3 6 "安装 Claude Code Commands → $CommandsDir"

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

if ($installed -ne $ExpectedSkillCount) {
    Write-Host "  ✗ Skill 数量异常：实际 $installed，期望 19 个 Claude Code 命令" -ForegroundColor Red
    exit 1
}

Write-Host "  共安装 $installed / $ExpectedSkillCount 个技能（期望 19 个 Claude Code 命令）"

Write-Host ""

# ---- 安装 Codex Skill ----
Write-Step 4 6 "安装 Codex Skill → $CodexSkillDest"

$codexSkillSrc = Join-Path $InstallDir "codex\$CodexSkillName"
if ($SkipCodex) {
    Write-Host "  已跳过"
} elseif (-not (Test-Path $codexSkillSrc)) {
    Write-Host "  ✗ 找不到 Codex Skill 目录: $codexSkillSrc" -ForegroundColor Red
    exit 1
} else {
    if (-not (Test-Path $CodexSkillsDir)) {
        New-Item -ItemType Directory -Path $CodexSkillsDir -Force | Out-Null
    }

    if (Test-Path $CodexSkillDest) {
        Remove-Item -LiteralPath $CodexSkillDest -Recurse -Force
    }

    Copy-Item -LiteralPath $codexSkillSrc -Destination $CodexSkillDest -Recurse -Force

    $codexRefSkillsDir = Join-Path $CodexSkillDest "references\skills"
    New-Item -ItemType Directory -Path $codexRefSkillsDir -Force | Out-Null
    Get-ChildItem -Path (Join-Path $skillsDir "*.md") | Copy-Item -Destination $codexRefSkillsDir -Force

    $codexToolsDir = Join-Path $CodexSkillDest "scripts\tools"
    New-Item -ItemType Directory -Path $codexToolsDir -Force | Out-Null
    $toolFiles = @(
        "financial_rigor.py",
        "report_audit.py",
        "stock_screener.py",
        "morningstar_fair_value.py",
        "ashare_data.py"
    )
    foreach ($toolFile in $toolFiles) {
        $srcTool = Join-Path $InstallDir "tools\$toolFile"
        if (Test-Path $srcTool) {
            Copy-Item -LiteralPath $srcTool -Destination $codexToolsDir -Force
        }
    }

    Write-Host "  已安装: $CodexSkillName"
    Write-Host "  Codex Home: $CodexHome"
}

Write-Host ""

# ---- Python 依赖 ----
Write-Step 5 6 "Python 工具依赖..."

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
Write-Step 6 6 "安装完成！"
Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ AI Berkshire 已就绪" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  安装目录: $InstallDir"
Write-Host "  Claude Code Commands: $CommandsDir"
if (-not $SkipCodex) {
    Write-Host "  Codex Skill:          $CodexSkillDest"
}
Write-Host "  已安装:               $installed / $ExpectedSkillCount 个 Claude Code 命令"
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
if (-not $SkipCodex) {
    Write-Host ""
    Write-Host "  Codex 提示:" -ForegroundColor Cyan
    Write-Host "    安装或更新 Codex Skill 后，请新开会话或重启 Codex App 再验证是否生效。"
}
Write-Host ""
