"""nnUNetTrainerCystFP_v2 — 修掉 v1 FTL 的稀釋問題,直接針對 cyst 假陽性。

v1 (nnUNetTrainerFTL_cyst) 的洞:FP 懲罰是「全批全域 Tversky」,cyst-negative 區的 FP voxel
被真囊腫的 TP+FN 淹掉 → βFP 這項幾乎沒梯度 → 沒真的在壓 FP。

v2 修正:非稀釋的「直接 FP-rate 懲罰」= 在『非 cyst 的 GT voxel』上的 cyst 機率均值。
- 對每個假陽性 voxel 都給梯度(不被 TP 稀釋);高信心 FP 貢獻最大 = voxel 層 hard-negative 強調。
- DC+CE 不動(仍保留 cyst Dice/recall)→ 若模型能『留住真囊腫、只砍假陽性』就會學到;
  若影像上不可分(β 預測),強 λ 會把 cyst 機率整體壓下 → 真囊腫 FN 上升。λ sweep 描出這條 trade-off。
- fullres(cyst 主導模型,98.8% voxel)從 baseline checkpoint fine-tune。
pre-reg: cystfp_v2_prereg_20260915.md。
"""
import numpy as np, torch, torch.nn as nn
from nnunetv2.training.loss.compound_losses import DC_and_CE_loss
from nnunetv2.training.loss.deep_supervision import DeepSupervisionWrapper
from nnunetv2.training.loss.dice import MemoryEfficientSoftDiceLoss
from nnunetv2.training.nnUNetTrainer.nnUNetTrainer import nnUNetTrainer
from nnunetv2.utilities.helpers import softmax_helper_dim1

CYST_CLASS_IDX = 3


class DirectFPCystPenalty(nn.Module):
    """非稀釋直接 FP 懲罰:mean(cyst_prob) over 非-cyst GT voxels。"""
    def __init__(self, cyst_class_idx: int = CYST_CLASS_IDX, smooth: float = 1e-5):
        super().__init__()
        self.c = cyst_class_idx
        self.smooth = smooth

    def forward(self, net_output: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        cyst_prob = softmax_helper_dim1(net_output)[:, self.c]      # (B,*)
        noncyst = (target[:, 0] != self.c).float()                  # (B,*) 非囊腫 GT
        return (cyst_prob * noncyst).sum() / (noncyst.sum() + self.smooth)


class DC_CE_FPpenalty(nn.Module):
    """standard DC+CE(所有類別,不動)+ λ · 直接 FP 懲罰(cyst)。"""
    def __init__(self, dc_ce_loss: nn.Module, lam_fp: float):
        super().__init__()
        self.dc_ce = dc_ce_loss
        self.fp = DirectFPCystPenalty()
        self.lam = lam_fp

    def forward(self, net_output, target):
        return self.dc_ce(net_output, target) + self.lam * self.fp(net_output, target)


class nnUNetTrainerCystFP_v2(nnUNetTrainer):
    LAM_FP = 3.0          # 由子類覆蓋
    def __init__(self, plans, configuration, fold, dataset_json, device=torch.device('cuda')):
        super().__init__(plans, configuration, fold, dataset_json, device)
        self.num_epochs = 250     # 從 baseline checkpoint fine-tune(-pretrained_weights)

    def _build_loss(self):
        if self.label_manager.has_regions:
            raise NotImplementedError("standard multi-class only (KiTS23 不走 region-based).")
        base = DC_and_CE_loss(
            {"batch_dice": self.configuration_manager.batch_dice, "smooth": 1e-5,
             "do_bg": False, "ddp": self.is_ddp}, {},
            weight_ce=1, weight_dice=1, ignore_label=self.label_manager.ignore_label,
            dice_class=MemoryEfficientSoftDiceLoss)
        loss = DC_CE_FPpenalty(base, self.LAM_FP)
        if self._do_i_compile():
            loss.dc_ce.dc = torch.compile(loss.dc_ce.dc)
        if self.enable_deep_supervision:
            ds = self._get_deep_supervision_scales()
            w = np.array([1 / (2 ** i) for i in range(len(ds))]); w[-1] = 0; w = w / w.sum()
            loss = DeepSupervisionWrapper(loss, w)
        return loss


class nnUNetTrainerCystFP_v2_l1(nnUNetTrainerCystFP_v2):
    LAM_FP = 1.0
class nnUNetTrainerCystFP_v2_l3(nnUNetTrainerCystFP_v2):
    LAM_FP = 3.0
class nnUNetTrainerCystFP_v2_l5(nnUNetTrainerCystFP_v2):
    LAM_FP = 5.0
class nnUNetTrainerCystFP_v2_l8(nnUNetTrainerCystFP_v2):
    LAM_FP = 8.0
