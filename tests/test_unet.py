import numpy as np
import pytest

torch = pytest.importorskip("torch")  # installed with the "unet" extra

from baraj_aynasi.unet import UNet, iou_f1, masked_loss, predict  # noqa: E402


def test_unet_output_shape():
    model = UNet(in_ch=6, base=8, depth=3)
    out = model(torch.zeros(2, 6, 48, 64))
    assert out.shape == (2, 1, 48, 64)


def test_predict_handles_sizes_not_divisible_by_16():
    torch.manual_seed(0)
    model = UNet(in_ch=6, base=8, depth=4)
    prob = predict(model, np.random.rand(6, 50, 37).astype(np.float32), "cpu")
    assert prob.shape == (50, 37)
    assert ((prob >= 0) & (prob <= 1)).all()


def test_masked_loss_ignores_masked_pixels():
    target = torch.zeros(1, 1, 2, 2)
    logits = torch.full((1, 1, 2, 2), -10.0)
    logits[0, 0, 0, 0] = 10.0  # a confident mistake...
    ignore = torch.zeros(1, 1, 2, 2, dtype=torch.bool)
    ignore[0, 0, 0, 0] = True  # ...on an ignored pixel
    assert masked_loss(logits, target, ignore).item() < 0.01
    assert masked_loss(logits, target, torch.zeros_like(ignore)).item() > 1.0


def test_iou_f1():
    pred = np.array([True, True, False, False])
    label = np.array([True, False, True, False])
    iou, f1 = iou_f1(pred, label, np.zeros(4, bool))
    assert iou == pytest.approx(1 / 3) and f1 == pytest.approx(0.5)
    iou, _ = iou_f1(pred, label, np.array([False, True, True, False]))
    assert iou == pytest.approx(1.0)
