#!/bin/bash
# H4 multi-seed robustness — pre-registered (h4_multiseed_prereg_20260918.md).
# nnU-Net v2 is non-deterministic (cudnn.benchmark, dataloader seeds=None), so an independent re-run
# of the identical fine-tune command = an independent seed draw (fixed init/split/LAM_FP; stochastic trajectory).
# Waits for the GPU to free (no nnUNetv2_train running), then runs N extra seeds for lam in {l3,l1},
# fullres-swap pipeline + eval each, archiving fold_0 -> fold_0_seed{k}.
set -uo pipefail
cd "${KITS23_ROOT:-$HOME/KiTS23}"
source "${KITS23_ROOT:-$HOME/KiTS23}/venv/bin/activate"
RESU="nnUNet_results/Dataset500_KiTS23"
BASE_FULL="$RESU/nnUNetTrainer__nnUNetPlans__3d_fullres/fold_0/checkpoint_final.pth"
EXTRA_SEEDS=3          # 每 λ 額外 seed 數(原單次跑=seed1)
LAMS=(l3 l1)
OUT=h4_multiseed_result.jsonl
ts(){ date '+%F %T'; }
log(){ echo "[$(ts)] $*"; }

# --- wait for GPU free (three-model λ=5 chain etc.) ---
log "等 GPU 空(輪詢 nnUNetv2_train 進程)..."
while pgrep -f 'venv/bin/nnUNetv2_train' >/dev/null 2>&1; do sleep 300; done
log "GPU 空,開始 H4 multi-seed。"

for lam in "${LAMS[@]}"; do
  TR="nnUNetTrainerCystFP_v2_${lam}"
  DIR="$RESU/${TR}__nnUNetPlans__3d_fullres"
  FOLD0="$DIR/fold_0"
  # seed1 = 原單次跑,先歸檔(保留其 validation 供記錄)
  if [ -d "$FOLD0" ] && [ ! -d "$DIR/fold_0_seed1" ]; then
    log "$lam: 歸檔原單次跑 -> fold_0_seed1"
    mv "$FOLD0" "$DIR/fold_0_seed1"
  fi
  for k in $(seq 2 $((EXTRA_SEEDS+1))); do
    log "==== $lam seed $k: 開始 fine-tune ===="
    rm -rf "$FOLD0"   # 確保全新(否則 nnU-Net 會 resume)
    # 不用 --npz:fullres-swap pipeline 只需 hard-label .nii.gz;--npz 會多存 ~48GB softmax
    nnUNetv2_train 500 3d_fullres 0 -tr "$TR" -p nnUNetPlans \
        -pretrained_weights "$BASE_FULL" > "logs_h4_${lam}_seed${k}_train.log" 2>&1
    rc=$?
    if [ $rc -ne 0 ] || [ ! -f "$FOLD0/checkpoint_final.pth" ]; then
      log "!! $lam seed $k 訓練失敗(rc=$rc),跳過"; continue
    fi
    VAL="$FOLD0/validation"
    nval=$(ls "$VAL"/*.nii.gz 2>/dev/null | wc -l)
    log "$lam seed $k 訓練完成,val nii=$nval;跑 pipeline+eval"
    TAG="h4_${lam}_s${k}"
    ./repro_check/rerun_pipeline_3model.sh "$VAL" "$TAG" > "logs_h4_${lam}_seed${k}_pipe.log" 2>&1
    # 抓最後(final)那次 eval 的 cyst FP 行 + HEC
    FINALEVAL=$(grep -A3 'final (expect' "logs_h4_${lam}_seed${k}_pipe.log" | grep -E 'HEC|cyst FP' )
    HECLINE=$(echo "$FINALEVAL" | grep HEC | tail -1)
    FPLINE=$(echo "$FINALEVAL" | grep 'cyst FP' | tail -1)
    log "$lam seed $k RESULT: $HECLINE | $FPLINE"
    echo "{\"lam\":\"$lam\",\"seed\":$k,\"hec\":\"$HECLINE\",\"fp\":\"$FPLINE\"}" >> "$OUT"
    # 只留 checkpoint_final + summary(provenance),刪 ~數GB 其餘,避免磁碟脹
    mkdir -p "$DIR/fold_0_seed${k}"
    cp "$FOLD0/checkpoint_final.pth" "$DIR/fold_0_seed${k}/" 2>/dev/null
    cp "$FOLD0/validation/summary.json" "$DIR/fold_0_seed${k}/" 2>/dev/null
    cp -r "$FOLD0/validation" "$DIR/fold_0_seed${k}/validation_nii" 2>/dev/null && rm -f "$DIR/fold_0_seed${k}/validation_nii"/*.npz 2>/dev/null
    rm -rf "$FOLD0"                         # 刪原始大 fold_0
    rm -rf "repro_check/scratch_${TAG}"    # 省磁碟
  done
done
log "H4 MULTISEED ALL DONE — 見 $OUT"
