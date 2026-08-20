#!/bin/bash
# Re-run the headline hold-out pipeline from raw predictions, with a swappable
# full-res source. Reproduction-check: FULLRES_SRC=raw fullres must reproduce
# hard_intersection 0.9022/19-of-48 and final 0.9020/16-of-48. FTL downstream:
# pass the FTL validation folder as FULLRES_SRC.
#   ./rerun_pipeline.sh <FULLRES_SRC_DIR> <TAG>
set -euo pipefail
# Local KiTS23 working root (raw data / weights obtained separately, not in this repo).
# Override with:  export KITS23_ROOT=/path/to/your/KiTS23
ROOT="${KITS23_ROOT:-$HOME/KiTS23}"
source "$ROOT/venv/bin/activate"
cd "$ROOT"
FULLRES_SRC="${1:-holdout_pipeline/raw_predictions/fullres}"
TAG="${2:-repro}"
REPRO="$ROOT/repro_check/scratch_${TAG}"
GT="$ROOT/nnUNet_preprocessed/Dataset500_KiTS23/gt_segmentations"
PP="KiTS23-2nd-place/nnunetv2/custom/postprocess.py"
PT="KiTS23-2nd-place/nnunetv2/custom/post_process_tumor.py"
ts(){ date '+%F %T'; }

echo "[$(ts)] === rerun_pipeline TAG=$TAG  FULLRES_SRC=$FULLRES_SRC ==="
rm -rf "$REPRO"; mkdir -p "$REPRO"
LOW="$REPRO/nnUNetTrainer__nnUNetPlans__3d_lowres/fold_0/validation"
FULL="$REPRO/nnUNetTrainer__nnUNetPlans__3d_fullres/fold_0/validation"
RES="$REPRO/nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/fold_0/validation"
mkdir -p "$LOW" "$FULL" "$RES"
cp holdout_pipeline/raw_predictions/lowres_plain/*.nii.gz "$LOW/"
cp holdout_pipeline/raw_predictions/resenc_l/*.nii.gz    "$RES/"
cp "$FULLRES_SRC"/*.nii.gz "$FULL/"
echo "[$(ts)] scratch ready: LOW/RES/FULL = $(ls "$LOW"|wc -l)/$(ls "$RES"|wc -l)/$(ls "$FULL"|wc -l)"

echo "[$(ts)] --- step1 pairA (postprocess.py -l lowres -f fullres) ---"
python "$PP" -l "$LOW" -f "$FULL"  > "$REPRO/step1_pairA.log" 2>&1
echo "[$(ts)] --- step1 pairB (postprocess.py -l resenc -f fullres) ---"
python "$PP" -l "$RES" -f "$FULL"  > "$REPRO/step1_pairB.log" 2>&1

echo "[$(ts)] --- step2 pairA (post_process_tumor.py) ---"
python "$PT" -l "$LOW/pp_kidney_fullres" -f "$FULL/pp_kidney_lowres"             > "$REPRO/step2_pairA.log" 2>&1
echo "[$(ts)] --- step2 pairB (post_process_tumor.py) ---"
python "$PT" -l "$RES/pp_kidney_fullres" -f "$FULL/pp_kidney_LPlans__3d_lowres"  > "$REPRO/step2_pairB.log" 2>&1

S2A="$FULL/pp_kidney_lowres/pp_tumor_union_lowres"
S2B="$FULL/pp_kidney_LPlans__3d_lowres/pp_tumor_union_LPlans__3d_lowres"
echo "[$(ts)] step2 outputs: pairA=$(ls "$S2A" 2>/dev/null|wc -l)  pairB=$(ls "$S2B" 2>/dev/null|wc -l)"

echo "[$(ts)] --- majority_vote([pairA,pairB], num_majority=2) -> hard_intersection ---"
HI="$REPRO/hard_intersection"
python -c "import sys; sys.path.insert(0,'$ROOT'); from p5_ablation import majority_vote; majority_vote(['$S2A','$S2B'], '$HI', 2)"
echo "[$(ts)] ### CHECKPOINT: hard_intersection (expect 0.9022 / 19-of-48) ###"
python repro_check/eval_hec_cystfp.py "$HI"

echo "[$(ts)] --- post_process_typeX.py (Rule3 min_vox<3 + TypeX t=0.7) -> final ---"
FINAL="$REPRO/final_rule3_typex"
python post_process_typeX.py --main "$HI" --raw-main "$FULL" --raw-chk "$RES" \
    --output "$FINAL" --gt "$GT" --typeX-thresh 0.7 --min-vox 3  > "$REPRO/typeX.log" 2>&1
echo "[$(ts)] ### CHECKPOINT: final (expect 0.9020 / 16-of-48) ###"
python repro_check/eval_hec_cystfp.py "$FINAL"
echo "[$(ts)] === DONE TAG=$TAG ==="
