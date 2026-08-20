#!/bin/bash
# R2 / Gap-3: per-model cyst FP-alarm + FN rate on TRAIN (391) and HOLD-OUT (98), read-only.
# hold-out side reuses existing fold_0/validation preds (TTA); train side predicts fresh (TTA)
# -> both sides same settings = apples-to-apples for the §4.4 train-vs-holdout ratio.
# Output train_fp_fn_recompute.json. Runs on the now-free GPU; does NOT touch pipeline products.
set -uo pipefail
cd /home/huaienyu/KiTS23
source venv/bin/activate
export nnUNet_raw="$HOME/KiTS23/nnUNet_raw" nnUNet_preprocessed="$HOME/KiTS23/nnUNet_preprocessed" nnUNet_results="$HOME/KiTS23/nnUNet_results"
PRE="$nnUNet_preprocessed/Dataset500_KiTS23"; RAW="$nnUNet_raw/Dataset500_KiTS23"; RES="$nnUNet_results/Dataset500_KiTS23"
GT="$PRE/gt_segmentations"
ts(){ date '+%F %T'; }
echo "[$(ts)] R2 START"

# fold0 train (391) — cv5.fold0 == canonical.fold0, so current cv5 split is fine
python3 -c "import json;d=json.load(open('$PRE/splits_final.json'));open('/tmp/r2_train.txt','w').write(''.join(c+chr(10) for c in sorted(d[0]['train'])))"
NTR=$(wc -l < /tmp/r2_train.txt); echo "[$(ts)] train cases = $NTR (expect 391)"

# input folder of 391 train images (symlink, read-only)
IN="repro_check/r2_train_imgs"; rm -rf "$IN"; mkdir -p "$IN"
while read c; do ln -sf "$RAW/imagesTr/${c}_0000.nii.gz" "$IN/"; done < /tmp/r2_train.txt

declare -A PLANS=( [lowres]="nnUNetPlans" [resenc]="nnUNetResEncUNetLPlans" )
for m in lowres resenc; do
  OUT="repro_check/r2_pred_${m}_train"
  if [ -f "$OUT/dataset.json" ] || [ "$(ls "$OUT"/*.nii.gz 2>/dev/null | wc -l)" -ge 391 ]; then
    echo "[$(ts)] $m train preds already present, skip predict"
  else
    echo "[$(ts)] predict $m train (391, default TTA)"
    rm -rf "$OUT"; mkdir -p "$OUT"
    nnUNetv2_predict -i "$IN" -o "$OUT" -d 500 -c 3d_lowres -tr nnUNetTrainer -p "${PLANS[$m]}" -f 0 \
      > "repro_check/r2_predict_${m}.log" 2>&1 || { echo "[$(ts)] !! $m predict failed"; exit 2; }
  fi
done

echo "[$(ts)] evaluating both sides..."
python3 r2_eval.py
echo "[$(ts)] R2 DONE -> train_fp_fn_recompute.json"
