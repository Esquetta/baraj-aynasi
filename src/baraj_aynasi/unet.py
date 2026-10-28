"""A small U-Net for water masks, its loss and whole-chip inference."""

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


def _block(cin: int, cout: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
        nn.Conv2d(cout, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    """Encoder-decoder with skip connections; `depth` halvings, so inputs must be
    divisible by 2**depth (whole chips are padded in `predict`)."""

    def __init__(self, in_ch: int = 6, base: int = 16, depth: int = 4):
        super().__init__()
        chans = [base * 2**i for i in range(depth + 1)]
        self.down = nn.ModuleList([_block(in_ch, chans[0])] + [_block(chans[i], chans[i + 1]) for i in range(depth)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(chans[i + 1], chans[i], 2, stride=2) for i in reversed(range(depth))])
        self.merge = nn.ModuleList([_block(chans[i] * 2, chans[i]) for i in reversed(range(depth))])
        self.head = nn.Conv2d(chans[0], 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for i, block in enumerate(self.down):
            x = block(x if i == 0 else F.max_pool2d(x, 2))
            skips.append(x)
        x = skips.pop()
        for up, merge in zip(self.up, self.merge):
            x = merge(torch.cat([up(x), skips.pop()], dim=1))
        return self.head(x)  # logits, shape (N, 1, H, W)


def masked_loss(logits: torch.Tensor, target: torch.Tensor, ignore: torch.Tensor) -> torch.Tensor:
    """Binary cross-entropy plus soft Dice, both over pixels not marked `ignore`."""
    keep = (~ignore).float()
    bce = F.binary_cross_entropy_with_logits(logits, target, reduction="none")
    bce = (bce * keep).sum() / keep.sum().clamp(min=1)
    p = torch.sigmoid(logits) * keep
    t = target * keep
    dice = 1 - (2 * (p * t).sum() + 1) / (p.sum() + t.sum() + 1)
    return bce + dice


@torch.no_grad()
def predict(model: nn.Module, x: np.ndarray, device: str, multiple: int = 16) -> np.ndarray:
    """Water probability for a whole chip (C, H, W); reflect-pads to a multiple of 16."""
    model.eval()
    _, h, w = x.shape
    ph, pw = (-h) % multiple, (-w) % multiple
    t = torch.from_numpy(x)[None].to(device)
    t = F.pad(t, (0, pw, 0, ph), mode="reflect")
    prob = torch.sigmoid(model(t))[0, 0, :h, :w]
    return prob.cpu().numpy()


def iou_f1(pred: np.ndarray, label: np.ndarray, ignore: np.ndarray) -> tuple[float, float]:
    """Intersection-over-union and F1 for water, over pixels not ignored."""
    keep = ~ignore
    p, t = pred[keep], label[keep]
    tp = np.count_nonzero(p & t)
    fp = np.count_nonzero(p & ~t)
    fn = np.count_nonzero(~p & t)
    iou = tp / (tp + fp + fn) if tp + fp + fn else 1.0
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0
    return iou, f1
