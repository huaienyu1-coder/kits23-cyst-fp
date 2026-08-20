# Gap 3 — 訓練集 cyst FP + FN 重算 provenance spec

*建立 2026-08-06 (CC)。用途:把 §4.4 中沒有計算產物的 32.1% / 29.5%(及 "vs 29.2%" 對照)*
*換成有 JSON 撐、可複現的數字。排在 CV folds 2–4 跑完之後執行(避免搶 GPU)。*

## 為什麼要重算(不是 reframe)

§4.4 "The errors are systematic, not overfitting" 用 train-set cyst FP 撐了**兩個**論點:
- **(a) systematic-not-overfitting**:train FP ≈ hold-out FP(比值 0.91–0.99)
- **(b) FP/FN 泛化不對稱**:cyst **FN** 有 train→hold-out gap,cyst **FP** 沒有

CV 跨-fold 只能接手 (a)(它比較的是不同 fold 的 hold-out,沒有 train 那一側),接不了 (b)。
直接拿掉 train 數字改用 CV 會讓 (b) 憑空失去證據 → 內容損失。**故重算,不 reframe。**

原始數字當初 abort 的原因是**磁碟不足**(ResEnc-L 對 391 train inference 只完成 ~19 case)。
現況磁碟 20% 用量、**1.3T 可用** → abort 前提已消失,重算又快又乾淨。

## 要產出的數字(對應 §4.4 原句)

原句:*"low-resolution **32.1%** vs 29.2%; residual **29.5%** vs 29.2%; ratios 0.91–0.99 … cyst false negatives show a train-to-hold-out generalization gap that the false positives do not."*

需要:每個模型在 **train(391)** 與 **hold-out(98)** 兩側各自的
**cyst FP alarm rate** 與 **cyst FN rate**(共 2 模型 × 2 側 × 2 指標 = 8 個數字 + 分子分母)。

> **待釐清的口徑(重算時一併定案)**:原句右側 "29.2%" 疑似 = hard-label 2/3-majority pipeline 的
> 14/48 = 29.2%(見 CLAUDE.md「Hard label 2/3 majority baseline … FP = 14/48 = 29.2%」),
> 若如此則左(per-model train)vs 右(pipeline hold-out)是 apples-to-oranges。
> **重算一律用 per-model 兩側對 per-model**,讓對照定義一致;若原 29.2% 確為 pipeline 數字,順帶修正 framing。

## 模型(路徑已確認存在,fold_0 = seed-45 hold-out 模型)

| §4.4 名稱 | nnUNet_results 路徑(Dataset500_KiTS23/…) | checkpoint |
|---|---|---|
| low-resolution | `nnUNetTrainer__nnUNetPlans__3d_lowres/fold_0` | checkpoint_final.pth ✓ |
| residual (ResEnc-L) | `nnUNetTrainer__nnUNetResEncUNetLPlans__3d_lowres/fold_0` | checkpoint_final.pth ✓ |

(§4.4 只點名這兩個模型 → 重算只跑這兩個,不擴充到 fullres,避免產生論文沒引用的數字。)

## 案例集(provenance 關鍵)

- **Train 側 = fold0 的 391 train case**。來源:`splits_final.json` fold0 `train`(seed=45 split)。
  已驗證:cv5.fold0 **==** canonical.fold0(391/98),union=489 → 這 391 case 在 cv5 或 canonical 下**完全相同**,
  故重算**不依賴** split 是否已還原成 canonical,只受 GPU 佔用限制。
- **Hold-out 側 = fold0 的 98 val case**(同一 split)。
- 影像:`nnUNet_raw/Dataset500_KiTS23/imagesTr/{case}_0000.nii.gz`;GT:`labelsTr/{case}.nii.gz`(已抽查存在)。
- 案例清單會存進輸出 JSON(count + sorted list)以便日後核對。

## Pipeline path(定死,防再出無 provenance 數字)

- **單模型 raw 預測**(`nnUNetv2_predict` 各模型獨立跑,**不經 Step1/Step2/voting/後處理**)——
  因為 §4.4 講的是 per-model(「low-resolution」「residual」)的 raw FP 行為,不是 pipeline 輸出。
- 預測 → argmax hard label → 用 **`repro_check/eval_hec_cystfp.py` 內同一套 cyst FP/FN 定義**:
  - **cyst FP alarm(case-level)**:該 case GT 無 cyst,但 pred 有 ≥1 個 cyst(label 3)connected component。
  - **cyst FN(case-level)**:該 case GT 有 cyst,但 pred 完全沒有 cyst。
  - 分母:FP alarm 用 GT-cyst-negative case 數;FN 用 GT-cyst-positive case 數。
- **唯讀** raw/GT/模型;輸出只寫到新 JSON,不動 pipeline 產物。

## 輸出

`train_fp_fn_recompute.json`,含 provenance header:
```
{ "generated": "<run 後補時間戳>",
  "models": {"lowres": "<path>", "resenc": "<path>"},
  "eval_def": "repro_check/eval_hec_cystfp.py cyst FP/FN, single-model raw argmax",
  "split": "seed45 fold0 (cv5.fold0==canonical), train=391 val=98",
  "cases_train": [...391...], "cases_holdout": [...98...],
  "results": { "lowres": {"train":{"fp":.., "fp_n":.., "fp_rate":.., "fn":.., "fn_n":.., "fn_rate":..},
                          "holdout":{...}},
               "resenc": {...} } }
```

## 排程 & 驗收

- **排在 CV folds 2–4 完成之後**跑(GPU 讓給 CV)。inference 量 = 2 模型 × (391+98) case,估 ~數小時。
- 驗收:若重算 train FP ≈ 32.1% / 29.5%(rounding 內)→ 直接把 §4.4 narrative 換成計算值。
  若**顯著不同** → 先查原因、**不**默默替換(避免又製造一個對不上的數字)。
- 改完 §4.4 後,把本檔 + JSON 一併放進 GitHub release 的 `analysis/` 供複現。
- 對照 [[project_kits23_state]] 與 CLAUDE.md「訓練集 FP 診斷」段(該段標「不完整」,重算後更新)。
