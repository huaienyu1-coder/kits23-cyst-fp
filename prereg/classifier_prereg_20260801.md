# Pre-registration — multivariate radiomic classifier on pooled residual FP
**狀態**:在跑 classifier 之前鎖定(locked before data)。目的就是防「跑完才決定怎麼寫」= p-hacking。
**日期**:2026-08-01(claude.ai 起草;operational 由 CC 執行)
**前置**:5-fold CV(folds 1-4 訓練中)完成後,pooled residual FP ≈ 130 才跑本分析。

> 一句話:這是 §8.5 capstone 的 N=26 → N≈130 升級版。它唯一能贏過 univariate 0.66 的缺口是**形態/紋理**(tumour 殘差不規則 vs 良性囊腫平滑)。跑,但判準先鎖死。

---

## 1. 這個實驗只回答一個問題
在 pipeline 判為 cyst 的 candidate 上,一個**多變量** hand-crafted 分類器,能不能把 residual false positive 從 true cyst 分開到「**有一個安全操作點**」——即某個決策規則,移掉 FP 而 true cyst 淨保留?

## 2. 資料 / 人口(pooled across 5 folds)
- **正例(要刪的)= residual FP components**:GT-negative case 內、pipeline 判 cyst 的 connected components。5 折各 ~26 → **pooled ≈ 130**。
- **反例(要保的)= TP cyst components**:pipeline 判 cyst 且與 GT cyst 重疊。5 折 pooled ≈ 880。
- **類別極不平衡(≈130:880)**——所以主指標是 base-rate-robust 的「TP-deleted per FP-removed」,不是 accuracy/AUC(見 §5)。
- 每個 component 標 **case ID + size(voxel)**(供 §4 的 group split 與 size 分層)。
- **【CC 補①】有效 N 是 case 數,不是 component 數**:130 個 FP component 來自約 **80 個 cyst-negative case**(~16/fold × 5)。GroupKFold **by case** 之下,泛化的獨立單位是 case,所以正例有效 N ≈ **80**,不是 130。「130」是 component 數,不可拿來估 power——這強化了 §4「只准簡單模型」與 §6「(a) 更可能」的先驗。報告時 N 用 case 數寫。
- **【CC 補③】前置條件(pooling 才成立)**:pooled 130 假設「每個 fold 的 cyst FP rate 都重現 fold-0 的 ~39.6%」。跑 classifier 前,先過 CV spot-check 確認 per-fold FP rate 落在合理帶內;若某 fold 大幅偏離,pooling 與 ceiling 泛化本身先有問題,要先處理,不能直接 pool。

## 3. 特徵集(先鎖,不得跑完再加)
與 §8.5 同一組 hand-crafted radiomic:first-order intensity(mean/std/percentiles HU)、shape(volume, extent, sphericity)、boundary-gradient sharpness、attenuation relative to surrounding parenchyma。**volume 要留但單獨標注**——它等於已部署的 size filter(Rule 3),不能算「新訊號」。

## 4. 分析協定(防 leakage 是紅線)
- **Nested cross-validation,outer/inner 都 GroupKFold by case(患者)**。同一 case 的多個 component **必須整組在同一 fold**——絕不可按 component 隨機切(那是 patient-level leakage,AUC 會虛高,正是本篇一路最怕的批評)。
- outer fold:估 held-out 效能 + 決定操作點是否 out-of-fold 成立;inner fold:選超參數 + **選操作點門檻**(門檻也是被 fit 的東西,必須 inner 選、outer 驗)。
- **模型複雜度上限先鎖**:N≈130 正例,只用**正則化的簡單模型**(logistic regression / 淺樹,少特徵)。禁止高容量模型、禁止 inner fold 外的 feature selection。
- **size 分層**:因 ~30-voxel blob 的 sphericity/紋理≈噪音,分析要**按 component size 分層報**(small vs large,門檻預先定如 median 或固定 vox)。多變量的希望只對大殘差成立;小殘差連多變量也沒可靠特徵——這點要能分開講。

## 5. 成功判準(先鎖死,不是 AUC)
- **成功 ≠ AUC > 0.5,也 ≠ 紙面 AUC 高。** 成功 = **outer-fold(held-out)上存在一個安全操作點**:移掉的 FP > 它刪掉的 true cyst(net positive),且在 held-out 而非 resubstitution 上成立。
- **【CC 補②】有意義門檻(跑前鎖)**:安全操作點還要**夠大才算數**——outer-fold 上安全地回收 **≥ 25% 的 residual FP**(且 true cyst 淨保留)才觸發 §6(b) 的 pivot;低於此(例如移掉 3/130、零代價)算 §6(a)「ceiling 確認,附註一個 marginal filter」。不鎖這個,一個瑣碎安全點會逼出「找到 filter 但幾乎沒用」的尷尬寫法。(25% 為預先設定的合理下限,可在跑前調,但**門檻必須存在且跑前定**。)
- 這與 §8.5 的判準完全同構(「no operating point removes more FP than the true cyst it deletes」),只是 N 從 26→130、從 univariate→multivariate。
- **對照 baseline**(都要 out-of-fold 比):(i) §8.5 的 univariate AUC≤0.66 / 無安全點;(ii) 已部署的 size filter(Rule 3)。「multivariate 贏 univariate」必須是 held-out 比較。

## 6. 兩種結果 —— 各自怎麼寫,現在就定
- **(a) outer-fold 上找不到安全操作點**(任何門檻移 FP 都刪掉 ≥ 等量 true cyst;**或只找到低於 §5 有意義門檻的瑣碎安全點**):
  → **ceiling 在 N≈130 確認**,論文最強版本。§8.5 從「N=26 不敢承重」升級成「即使多變量、即使 N=130,也沒有安全操作點」。thesis 不變(irreducible by image-only means / no usable operating point)。
- **(b) outer-fold 上存在安全操作點,且回收率 ≥ §5 有意義門檻**(移 X% FP ≥ 25%、代價 Y% true cyst,net positive):
  → 論文從純 negative **pivot 成 mixed/positive**:「a radiomic post-hoc filter recovers X% of residual FP at Y cost」。這是 major reframe,thesis 要改寫;**且策略上要清醒**——它把論文推向擁擠的 radiomic-filter genre,對頂刊的獨特性反而是稀釋(見先前討論),即使它「改進了 cyst」。**不是災難,但不是免費的好消息。**
- **紅線**:(a)/(b) 的判定只看 §5 的 outer-fold 安全操作點,**跑之前定,跑完不得改判準**。

## 7. 不論結果都要報的
- outer-fold AUC + CI(size 分層),明標「AUC 是 illustration,判準是操作點」(對齊 §8.6 的 no-usable-operating-point framing)。
- FP-removed vs TP-deleted 的 trade-off 曲線(held-out),按 size 分層。
- 與 univariate(§8.5)、size filter(Rule 3)的 out-of-fold 對照。
- 明標類別不平衡(≈130:880)與所用的 base-rate-robust 指標。

## 8. 紅線彙總
- GroupKFold **by case**,永不 by component。
- 操作點在 inner 選、outer 驗;report held-out,不 report resubstitution。
- 模型複雜度上限、無 inner 外 feature selection。
- volume 特徵單獨標(= Rule 3,不算新訊號)。
- 判準 = safe operating point,不是 AUC;(a)/(b) 寫法跑前鎖定。
- **有效 N 用 case 數(≈80)寫,不用 component 數(130)高估 power。**
- **(b) 需回收率 ≥ 25% 有意義門檻才觸發 pivot;瑣碎安全點算 (a)。**
- pooling 前先過 per-fold FP-rate 重現 spot-check。
- CV 數字永不與第二名 hidden-test 頭對頭。

---
*本檔為新增 pre-reg,未改動任何 data/pipeline。operational(特徵抽取、nested-CV 實作)由 CC 執行,framing/判準由本檔鎖定。*
*2026-08-01 CC 折入補①(有效 N=case 數)、補②(有意義門檻 ≥25%)、補③(per-fold FP-rate 前置條件),見各節 【CC 補】標記。*
