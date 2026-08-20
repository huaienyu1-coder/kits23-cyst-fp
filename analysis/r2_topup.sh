#!/bin/bash
# R2 top-up: predict any TRAIN case missing from r2_pred_{model}_train (the 1 dropped by the
# no-trailing-newline off-by-one), for both models, then re-eval on the full 391. Run AFTER the
# main R2 driver finishes. Fix-not-annotate: the artifact must cover all 391 train cases.
set -uo pipefail
cd /home/huaienyu/KiTS23; source venv/bin/activate
export nnUNet_raw="$HOME/KiTS23/nnUNet_raw" nnUNet_preprocessed="$HOME/KiTS23/nnUNet_preprocessed" nnUNet_results="$HOME/KiTS23/nnUNet_results"
PRE="$nnUNet_preprocessed/Dataset500_KiTS23"; RAW="$nnUNet_raw/Dataset500_KiTS23"
python3 -c "import json;d=json.load(open('$PRE/splits_final.json'));print('\n'.join(sorted(d[0]['train'])))" > /tmp/r2_train_full.txt
declare -A PLANS=( [lowres]="nnUNetPlans" [resenc]="nnUNetResEncUNetLPlans" )
for m in lowres resenc; do
  OUT="repro_check/r2_pred_${m}_train"
  MISS="repro_check/r2_topup_${m}_in"; rm -rf "$MISS"; mkdir -p "$MISS"; miss=0
  while read c; do
    [ -f "$OUT/${c}.nii.gz" ] || { ln -sf "$RAW/imagesTr/${c}_0000.nii.gz" "$MISS/"; miss=$((miss+1)); }
  done < /tmp/r2_train_full.txt
  echo "$m: $miss missing case(s) to top up"
  if [ "$miss" -gt 0 ]; then
    nnUNetv2_predict -i "$MISS" -o "$OUT" -d 500 -c 3d_lowres -tr nnUNetTrainer -p "${PLANS[$m]}" -f 0 >> "repro_check/r2_predict_${m}.log" 2>&1
  fi
  echo "$m: now $(ls "$OUT"/*.nii.gz 2>/dev/null | wc -l)/391 train preds"
done
echo "re-eval on full 391..."
python3 r2_eval.py
