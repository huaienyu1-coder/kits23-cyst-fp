<#
.SYNOPSIS
    YouTube 去廣告：用瀏覽器「政策」自動幫 Chrome / Edge / Firefox 裝好擋廣告擴充功能。

.DESCRIPTION
    會安裝的擴充功能（全部免費、開源、在官方商店上架）：
      Chrome  : uBlock Origin Lite + SponsorBlock   （Chrome Web Store）
      Edge    : uBlock Origin Lite + SponsorBlock   （Microsoft Edge Add-ons）
      Firefox : uBlock Origin（完整版）+ SponsorBlock（addons.mozilla.org）

    做法：在 HKLM\SOFTWARE\Policies 底下寫入各瀏覽器的 ExtensionSettings 政策，
    installation_mode = normal_installed（自動安裝，但你仍可在瀏覽器裡停用）。
    你原本已有的其他 ExtensionSettings 項目會被保留，本腳本只新增 / 移除自己的項目。

.EXAMPLE
    .\youtube-adblock.ps1 -Action Install
.EXAMPLE
    .\youtube-adblock.ps1 -Action Install -NoSponsorBlock -SkipEdge
.EXAMPLE
    .\youtube-adblock.ps1 -Action Status
.EXAMPLE
    .\youtube-adblock.ps1 -Action Uninstall
#>
[CmdletBinding()]
param(
    [ValidateSet('Install', 'Uninstall', 'Status')]
    [string]$Action = 'Install',
    [switch]$NoSponsorBlock,
    [switch]$SkipChrome,
    [switch]$SkipEdge,
    [switch]$SkipFirefox,
    [switch]$NoPause
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

if ($env:OS -ne 'Windows_NT') {
    Write-Host '這個腳本只適用於 Windows。macOS 請用 macos\youtube-adblock.mobileconfig，Linux 請用 linux/youtube-adblock.sh。' -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
$ChromeStore = 'https://clients2.google.com/service/update2/crx'
$EdgeStore   = 'https://edge.microsoft.com/extensionwebstorebase/v1/crx'
$AmoLatest   = 'https://addons.mozilla.org/firefox/downloads/latest'

function New-Ext([string]$Id, [string]$Label, [bool]$IsSponsorBlock, [hashtable]$Settings) {
    return @{ Id = $Id; Label = $Label; IsSponsorBlock = $IsSponsorBlock; Settings = $Settings }
}

$Targets = @(
    @{
        Name     = 'Google Chrome'
        Skip     = [bool]$SkipChrome
        Key      = 'HKLM:\SOFTWARE\Policies\Google\Chrome'
        MultiSz  = $false
        CheckUrl = 'chrome://policy'
        Exe      = @('Google\Chrome\Application\chrome.exe')
        Exts     = @(
            (New-Ext 'ddkjiahejlhfcafbddmgiahcphecmpfh' 'uBlock Origin Lite' $false @{ installation_mode = 'normal_installed'; update_url = $ChromeStore }),
            (New-Ext 'mnjggcdmjocbbbhaepdhchncahnbgone' 'SponsorBlock'       $true  @{ installation_mode = 'normal_installed'; update_url = $ChromeStore })
        )
    },
    @{
        Name     = 'Microsoft Edge'
        Skip     = [bool]$SkipEdge
        Key      = 'HKLM:\SOFTWARE\Policies\Microsoft\Edge'
        MultiSz  = $false
        CheckUrl = 'edge://policy'
        Exe      = @('Microsoft\Edge\Application\msedge.exe')
        Exts     = @(
            (New-Ext 'cimighlppcgcoapaliogpjjdehbnofhn' 'uBlock Origin Lite' $false @{ installation_mode = 'normal_installed'; update_url = $EdgeStore }),
            (New-Ext 'mbmgnelfcpoecdepckhlhegpcehmpmji' 'SponsorBlock'       $true  @{ installation_mode = 'normal_installed'; update_url = $EdgeStore })
        )
    },
    @{
        Name     = 'Mozilla Firefox'
        Skip     = [bool]$SkipFirefox
        Key      = 'HKLM:\SOFTWARE\Policies\Mozilla\Firefox'
        MultiSz  = $true   # Firefox 官方範本使用 REG_MULTI_SZ
        CheckUrl = 'about:policies'
        Exe      = @('Mozilla Firefox\firefox.exe')
        Exts     = @(
            (New-Ext 'uBlock0@raymondhill.net' 'uBlock Origin' $false @{ installation_mode = 'normal_installed'; install_url = "$AmoLatest/ublock-origin/latest.xpi" }),
            (New-Ext 'sponsorBlocker@ajay.app' 'SponsorBlock'  $true  @{ installation_mode = 'normal_installed'; install_url = "$AmoLatest/sponsorblock/latest.xpi" })
        )
    }
)

# ---------------------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------------------
function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-BrowserInstalled([string[]]$RelativePaths) {
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA) | Where-Object { $_ }
    foreach ($root in $roots) {
        foreach ($rel in $RelativePaths) {
            if (Test-Path -LiteralPath (Join-Path $root $rel)) { return $true }
        }
    }
    return $false
}

# 讀取現有的 ExtensionSettings（JSON 字串），回傳 hashtable：擴充 ID -> 設定
function Read-ExtensionSettings([string]$Key) {
    $result = @{}
    if (-not (Test-Path -LiteralPath $Key)) { return , $result }
    $prop = Get-ItemProperty -LiteralPath $Key -Name 'ExtensionSettings' -ErrorAction SilentlyContinue
    if ($null -eq $prop) { return , $result }
    $raw = $prop.ExtensionSettings
    if ($raw -is [array]) { $raw = $raw -join "`n" }
    if ([string]::IsNullOrWhiteSpace($raw)) { return , $result }
    try {
        $obj = $raw | ConvertFrom-Json
    } catch {
        throw "$Key 裡的 ExtensionSettings 不是合法 JSON。為避免覆蓋你原本的設定，已停止，沒有做任何變更。"
    }
    foreach ($p in $obj.PSObject.Properties) { $result[$p.Name] = $p.Value }
    return , $result
}

function Write-ExtensionSettings([string]$Key, [hashtable]$Settings, [bool]$MultiSz) {
    if ($Settings.Count -eq 0) {
        if (Test-Path -LiteralPath $Key) {
            Remove-ItemProperty -LiteralPath $Key -Name 'ExtensionSettings' -ErrorAction SilentlyContinue
        }
        return
    }
    if (-not (Test-Path -LiteralPath $Key)) { New-Item -Path $Key -Force | Out-Null }
    $json = ConvertTo-Json -InputObject $Settings -Depth 10 -Compress
    if ($MultiSz) {
        New-ItemProperty -LiteralPath $Key -Name 'ExtensionSettings' -PropertyType MultiString -Value ([string[]]@($json)) -Force | Out-Null
    } else {
        New-ItemProperty -LiteralPath $Key -Name 'ExtensionSettings' -PropertyType String -Value $json -Force | Out-Null
    }
}

function Pause-IfNeeded {
    if (-not $NoPause) { [void](Read-Host '按 Enter 關閉視窗') }
}

# ---------------------------------------------------------------------------
# 需要管理員權限（寫入 HKLM）。不是管理員就用 UAC 重新啟動自己。
# ---------------------------------------------------------------------------
if ($Action -ne 'Status' -and -not (Test-IsAdmin)) {
    Write-Host '需要系統管理員權限，正在要求提升權限（UAC 視窗請按「是」）...' -ForegroundColor Yellow
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath), '-Action', $Action)
    foreach ($name in 'NoSponsorBlock', 'SkipChrome', 'SkipEdge', 'SkipFirefox', 'NoPause') {
        if ($PSBoundParameters.ContainsKey($name)) { $argList += "-$name" }
    }
    $hostExe = (Get-Process -Id $PID).Path
    try {
        Start-Process -FilePath $hostExe -Verb RunAs -ArgumentList $argList | Out-Null
        exit 0
    } catch {
        Write-Host '已取消或無法取得管理員權限，沒有做任何變更。' -ForegroundColor Red
        Pause-IfNeeded
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------
$exitCode = 0
try {
    Write-Host ''
    Write-Host "=== YouTube 去廣告部署工具（$Action）===" -ForegroundColor Cyan

    foreach ($t in $Targets) {
        Write-Host ''
        Write-Host "[$($t.Name)]" -ForegroundColor Cyan
        if ($t.Skip) { Write-Host '  已略過（依參數指定）'; continue }
        if (-not (Test-BrowserInstalled $t.Exe)) {
            Write-Host '  （沒偵測到這個瀏覽器；仍會寫入政策，日後安裝就會自動生效）' -ForegroundColor DarkGray
        }

        $current = Read-ExtensionSettings $t.Key

        switch ($Action) {
            'Install' {
                foreach ($e in $t.Exts) {
                    if ($e.IsSponsorBlock -and $NoSponsorBlock) { continue }
                    $current[$e.Id] = $e.Settings
                    Write-Host "  + $($e.Label)  ($($e.Id))" -ForegroundColor Green
                }
                Write-ExtensionSettings $t.Key $current $t.MultiSz
            }
            'Uninstall' {
                foreach ($e in $t.Exts) {
                    if ($current.ContainsKey($e.Id)) {
                        $current.Remove($e.Id)
                        Write-Host "  - $($e.Label)  ($($e.Id))" -ForegroundColor Yellow
                    }
                }
                Write-ExtensionSettings $t.Key $current $t.MultiSz
            }
            'Status' {
                foreach ($e in $t.Exts) {
                    $state = if ($current.ContainsKey($e.Id)) { '已設定' } else { '未設定' }
                    Write-Host ("  {0,-20} {1}" -f $e.Label, $state)
                }
                $others = @($current.Keys | Where-Object { $id = $_; -not ($t.Exts | Where-Object { $_.Id -eq $id }) })
                if ($others.Count -gt 0) { Write-Host "  （另有其他擴充政策 $($others.Count) 項，本工具不會動到）" -ForegroundColor DarkGray }
            }
        }
    }

    Write-Host ''
    switch ($Action) {
        'Install' {
            Write-Host '完成！接下來：' -ForegroundColor Green
            Write-Host '  1. 把 Chrome / Edge / Firefox「完全關閉」後再打開（含右下角背景執行的）。'
            Write-Host '  2. 等大約 1 分鐘，擴充功能會自動出現在工具列的拼圖選單裡。'
            Write-Host '  3. 想確認政策有生效：在網址列輸入 chrome://policy、edge://policy 或 about:policies。'
            Write-Host '  * 瀏覽器顯示「由貴機構管理」是正常的（因為使用了政策），執行 uninstall.cmd 即可移除。'
        }
        'Uninstall' {
            Write-Host '已移除本工具寫入的政策。重開瀏覽器後生效。' -ForegroundColor Green
            Write-Host '若擴充功能仍留在瀏覽器裡，可到擴充功能頁面手動移除。'
        }
    }
} catch {
    Write-Host ''
    Write-Host "發生錯誤：$($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
} finally {
    Pause-IfNeeded
}
exit $exitCode
