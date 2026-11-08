#!/usr/bin/env bash
# YouTube 去廣告：Linux 一鍵部署
#
# 透過瀏覽器「政策」自動安裝擋廣告擴充功能：
#   Chrome / Chromium : uBlock Origin Lite + SponsorBlock（Chrome Web Store）
#   Microsoft Edge    : uBlock Origin Lite + SponsorBlock（Edge Add-ons）
#   Firefox           : uBlock Origin（完整版）+ SponsorBlock（addons.mozilla.org）
#
# 用法：
#   sudo bash youtube-adblock.sh install [--no-sponsorblock]
#   sudo bash youtube-adblock.sh status
#   sudo bash youtube-adblock.sh uninstall
#
# installation_mode 使用 normal_installed：自動安裝，但你仍可在瀏覽器裡停用。
# Firefox 的 policies.json 若已存在，會「合併」而不是覆蓋（並先備份一份）。
# 不支援 Flatpak 版瀏覽器（它們讀不到 /etc 底下的政策），請改用手動安裝。
set -euo pipefail

ACTION="install"
NO_SPONSORBLOCK=0
ORIG_ARGS=("$@")
for arg in "$@"; do
  case "$arg" in
    install|uninstall|status) ACTION="$arg" ;;
    --no-sponsorblock) NO_SPONSORBLOCK=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知參數：$arg（用 --help 看說明）" >&2; exit 2 ;;
  esac
done

POLICY_FILE="youtube-adblock.json"
CHROME_STORE="https://clients2.google.com/service/update2/crx"
EDGE_STORE="https://edge.microsoft.com/extensionwebstorebase/v1/crx"

UBOL_CWS="ddkjiahejlhfcafbddmgiahcphecmpfh"   # uBlock Origin Lite（Chrome Web Store）
SB_CWS="mnjggcdmjocbbbhaepdhchncahnbgone"     # SponsorBlock（Chrome Web Store）
UBOL_EDGE="cimighlppcgcoapaliogpjjdehbnofhn"  # uBlock Origin Lite（Edge Add-ons）
SB_EDGE="mbmgnelfcpoecdepckhlhegpcehmpmji"    # SponsorBlock（Edge Add-ons）

# 測試用：設定 YOUTUBE_ADBLOCK_ROOT=/某個/資料夾，所有檔案就會寫到那底下，而不是真的 /etc
R="${YOUTUBE_ADBLOCK_ROOT:-}"

# Chromium 系列的政策資料夾（每個瀏覽器各放一個獨立 JSON 檔，不會動到你其他的政策檔）
CHROME_DIRS=("$R/etc/opt/chrome/policies/managed" "$R/etc/chromium/policies/managed")
# Ubuntu 的 snap 版 Chromium 讀的是 /etc/chromium-browser
if [[ -d "$R/etc/chromium-browser" ]] || { command -v snap >/dev/null 2>&1 && snap list chromium >/dev/null 2>&1; }; then
  CHROME_DIRS+=("$R/etc/chromium-browser/policies/managed")
fi
EDGE_DIRS=("$R/etc/opt/edge/policies/managed")
FIREFOX_POLICY="$R/etc/firefox/policies/policies.json"

if [[ $EUID -ne 0 && "$ACTION" != "status" ]]; then
  echo "需要 root 權限，改用 sudo 重新執行..."
  exec sudo bash "$0" "${ORIG_ARGS[@]}"
fi

# 產生 Chromium 系列的政策 JSON：$1=uBOL ID  $2=SponsorBlock ID  $3=商店更新網址
chromium_policy_json() {
  local sb=""
  if [[ "$NO_SPONSORBLOCK" != 1 ]]; then
    sb=$(printf ',\n    "%s": { "installation_mode": "normal_installed", "update_url": "%s" }' "$2" "$3")
  fi
  cat <<EOF
{
  "ExtensionSettings": {
    "$1": { "installation_mode": "normal_installed", "update_url": "$3" }$sb
  }
}
EOF
}

warn_conflicts() {
  # 同一個資料夾裡若有別的檔案也設定 ExtensionSettings，Chrome 只會採用其中一個
  local dir="$1" f
  for f in "$dir"/*.json; do
    [[ -e "$f" && "$(basename "$f")" != "$POLICY_FILE" ]] || continue
    if grep -q '"ExtensionSettings"' "$f" 2>/dev/null; then
      echo "  ⚠ $f 也設定了 ExtensionSettings，可能互相覆蓋，請手動合併。"
    fi
  done
}

# Firefox：合併 / 移除 policies.json 裡本工具的項目。$1=install|uninstall
firefox_policy() {
  if ! command -v python3 >/dev/null 2>&1; then
    if [[ -e "$FIREFOX_POLICY" ]]; then
      echo "  ⚠ 找不到 python3，無法安全合併既有的 $FIREFOX_POLICY，已略過 Firefox。"
      return 0
    fi
    [[ "$1" == "install" ]] || return 0
    mkdir -p "$(dirname "$FIREFOX_POLICY")"
    local sb=""
    [[ "$NO_SPONSORBLOCK" == 1 ]] || sb=',
      "sponsorBlocker@ajay.app": { "installation_mode": "normal_installed", "install_url": "https://addons.mozilla.org/firefox/downloads/latest/sponsorblock/latest.xpi" }'
    cat > "$FIREFOX_POLICY" <<EOF
{
  "policies": {
    "ExtensionSettings": {
      "uBlock0@raymondhill.net": { "installation_mode": "normal_installed", "install_url": "https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/latest.xpi" }$sb
    }
  }
}
EOF
    return 0
  fi

  mkdir -p "$(dirname "$FIREFOX_POLICY")"
  if [[ "$1" == "install" && -e "$FIREFOX_POLICY" && ! -e "$FIREFOX_POLICY.bak-youtube-adblock" ]]; then
    cp -p "$FIREFOX_POLICY" "$FIREFOX_POLICY.bak-youtube-adblock"
    echo "  已備份原本的設定到 $FIREFOX_POLICY.bak-youtube-adblock"
  fi
  python3 -I - "$FIREFOX_POLICY" "$1" "$NO_SPONSORBLOCK" <<'PY'
import json, os, sys

path, action, no_sb = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
amo = "https://addons.mozilla.org/firefox/downloads/latest"
ours = {
    "uBlock0@raymondhill.net": {"installation_mode": "normal_installed",
                                "install_url": amo + "/ublock-origin/latest.xpi"},
    "sponsorBlocker@ajay.app": {"installation_mode": "normal_installed",
                                "install_url": amo + "/sponsorblock/latest.xpi"},
}

data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if text.strip():
        data = json.loads(text)  # 原檔若不是合法 JSON 會直接報錯，不會覆蓋

policies = data.setdefault("policies", {})
ext = policies.setdefault("ExtensionSettings", {})
if action == "install":
    for ext_id, cfg in ours.items():
        if no_sb and ext_id == "sponsorBlocker@ajay.app":
            continue
        ext[ext_id] = cfg
else:
    for ext_id in ours:
        ext.pop(ext_id, None)
    if not ext:
        policies.pop("ExtensionSettings")
    if not policies:
        data.pop("policies")

if data:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
elif os.path.exists(path):
    os.remove(path)
PY
}

case "$ACTION" in
  install)
    echo "=== 安裝 YouTube 去廣告政策 ==="
    for dir in "${CHROME_DIRS[@]}"; do
      mkdir -p "$dir"
      chromium_policy_json "$UBOL_CWS" "$SB_CWS" "$CHROME_STORE" > "$dir/$POLICY_FILE"
      chmod 644 "$dir/$POLICY_FILE"
      echo "  + Chrome/Chromium: $dir/$POLICY_FILE"
      warn_conflicts "$dir"
    done
    for dir in "${EDGE_DIRS[@]}"; do
      mkdir -p "$dir"
      chromium_policy_json "$UBOL_EDGE" "$SB_EDGE" "$EDGE_STORE" > "$dir/$POLICY_FILE"
      chmod 644 "$dir/$POLICY_FILE"
      echo "  + Edge:            $dir/$POLICY_FILE"
      warn_conflicts "$dir"
    done
    firefox_policy install
    echo "  + Firefox:         $FIREFOX_POLICY"
    echo
    echo "完成！把瀏覽器完全關閉再打開，約 1 分鐘內擴充功能會自動出現。"
    echo "確認方式：網址列輸入 chrome://policy、edge://policy 或 about:policies"
    ;;
  uninstall)
    echo "=== 移除 YouTube 去廣告政策 ==="
    for dir in "${CHROME_DIRS[@]}" "${EDGE_DIRS[@]}"; do
      if [[ -e "$dir/$POLICY_FILE" ]]; then
        rm -f "$dir/$POLICY_FILE"
        echo "  - $dir/$POLICY_FILE"
      fi
    done
    if [[ -e "$FIREFOX_POLICY" ]]; then
      firefox_policy uninstall
      echo "  - Firefox: 已從 $FIREFOX_POLICY 移除本工具的項目"
    fi
    echo "完成。重開瀏覽器後生效；擴充功能若仍在，可到擴充功能頁面手動移除。"
    ;;
  status)
    for dir in "${CHROME_DIRS[@]}" "${EDGE_DIRS[@]}"; do
      if [[ -e "$dir/$POLICY_FILE" ]]; then echo "已設定  $dir/$POLICY_FILE"; else echo "未設定  $dir/$POLICY_FILE"; fi
    done
    if [[ -e "$FIREFOX_POLICY" ]] && grep -q 'uBlock0@raymondhill.net' "$FIREFOX_POLICY"; then
      echo "已設定  $FIREFOX_POLICY"
    else
      echo "未設定  $FIREFOX_POLICY"
    fi
    ;;
esac
