#!/usr/bin/env bash
# 自架 Invidious 一鍵部署：產生隨機密鑰 → 拉映像檔 → 啟動
# 用法：bash setup.sh
# 更新：docker compose pull && docker compose up -d
# 停止：docker compose down
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "找不到 docker。請先安裝 Docker：https://docs.docker.com/engine/install/" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "找不到 docker compose 外掛。請安裝 Docker Compose v2。" >&2
  exit 1
fi

# 2N 個十六進位字元的隨機字串（od 只讀固定位元組數，不會有 SIGPIPE 問題）
rand_hex() { od -An -tx1 -N"$1" /dev/urandom | tr -d ' \n'; }

if [[ ! -f .env ]]; then
  umask 077
  cat > .env <<EOF
# 由 setup.sh 自動產生的密鑰。請勿分享或 commit（已在 .gitignore 中排除）。
# invidious_companion_key 規定必須剛好 16 個字元
COMPANION_KEY=$(rand_hex 8)
HMAC_KEY=$(rand_hex 20)
POSTGRES_PASSWORD=$(rand_hex 16)

# 只給這台電腦用：保持 127.0.0.1
# 要讓家裡其他裝置（手機、電視、平板）也能用：改成 0.0.0.0，然後 docker compose up -d
# 不要直接開放到網際網路；要外連請自行加上 HTTPS 反向代理。
INVIDIOUS_BIND=127.0.0.1
INVIDIOUS_PORT=3000
EOF
  echo "已產生 .env（隨機密鑰）"
else
  echo "沿用既有的 .env"
fi

docker compose pull
docker compose up -d

port=$(grep -E '^INVIDIOUS_PORT=' .env | cut -d= -f2)
echo
echo "完成！打開瀏覽器到 http://localhost:${port:-3000}"
echo "第一次啟動資料庫需要約 30 秒初始化；若打不開請稍等再重新整理。"
echo "查看狀態：docker compose ps    查看日誌：docker compose logs -f invidious companion"
