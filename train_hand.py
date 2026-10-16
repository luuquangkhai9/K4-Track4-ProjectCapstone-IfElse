"""
Huan luyen bo phat hien 21 keypoint ban tay tren CMU Panoptic Hand Dataset
(Simon et al., "Hand Keypoint Detection in Single Images using Multiview Bootstrapping", CVPR 2017).

Tai dataset: http://domedb.perception.cs.cmu.edu/handdb.html
  - hand_labels.zip       (nhan thu cong: manual_train / manual_test)
  - hand_labels_synth.zip (tuy chon, du lieu tong hop)
Moi anh .jpg co file .json cung ten, chua "hand_pts": 21 x [x, y, visible].

Chay:
  python train_hand.py --root /path/hand_labels --epochs 60
"""
import argparse, glob, json, os, random
import cv2, numpy as np, torch, torch.nn as nn, torchvision
from torch.utils.data import Dataset, DataLoader

NUM_KP, IN, HM = 21, 256, 64
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)

HAND_EDGES = [(0, 1), (1, 2), (2, 3), (3, 4),
              (0, 5), (5, 6), (6, 7), (7, 8),
              (0, 9), (9, 10), (10, 11), (11, 12),
              (0, 13), (13, 14), (14, 15), (15, 16),
              (0, 17), (17, 18), (18, 19), (19, 20)]


def make_affine(center, size, rot_deg=0.0, out=IN):
    """Ma tran affine dua vung vuong (center,size) ve anh out x out."""
    M = cv2.getRotationMatrix2D((float(center[0]), float(center[1])), rot_deg, out / float(size))
    M[0, 2] += out / 2 - center[0]
    M[1, 2] += out / 2 - center[1]
    return M


def to_tensor(rgb):
    x = (rgb.astype(np.float32) / 255.0 - MEAN) / STD
    return torch.from_numpy(x.transpose(2, 0, 1).copy())


class CMUHand(Dataset):
    def __init__(self, root, split="manual_train", train=True):
        self.files = sorted(glob.glob(os.path.join(root, split, "*.json")))
        assert self.files, f"Khong tim thay json trong {root}/{split}"
        self.train = train

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        jp = self.files[i]
        ann = json.load(open(jp))
        img = cv2.imread(os.path.splitext(jp)[0] + ".jpg")[:, :, ::-1]
        pts = np.array(ann["hand_pts"], np.float32)
        xy, vis = pts[:, :2], pts[:, 2] > 0
        pv = xy[vis]
        c = (pv.max(0) + pv.min(0)) / 2
        size = max((pv.max(0) - pv.min(0)).max() * 1.6, 32)
        rot = 0.0
        if self.train:
            c = c + np.random.uniform(-0.08, 0.08, 2) * size
            size *= np.random.uniform(0.85, 1.25)
            rot = np.random.uniform(-40, 40)
        M = make_affine(c, size, rot)
        crop = cv2.warpAffine(np.ascontiguousarray(img), M, (IN, IN))
        kp = xy @ M[:, :2].T + M[:, 2]
        if self.train and random.random() < 0.5:
            crop = crop[:, ::-1]
            kp[:, 0] = IN - 1 - kp[:, 0]
        if self.train:  # jitter mau sac
            crop = np.clip(crop.astype(np.float32) * np.random.uniform(0.7, 1.3)
                           + np.random.uniform(-20, 20), 0, 255)
        k = kp * HM / IN
        valid = vis & (k[:, 0] >= 0) & (k[:, 0] < HM) & (k[:, 1] >= 0) & (k[:, 1] < HM)
        gx, gy = np.meshgrid(np.arange(HM), np.arange(HM))
        hm = np.zeros((NUM_KP, HM, HM), np.float32)
        for j in range(NUM_KP):
            if valid[j]:
                hm[j] = np.exp(-((gx - k[j, 0]) ** 2 + (gy - k[j, 1]) ** 2) / (2 * 2.0 ** 2))
        return to_tensor(np.ascontiguousarray(crop)), torch.from_numpy(hm), \
            torch.from_numpy(valid.astype(np.float32)), torch.from_numpy(kp.astype(np.float32))


class HandNet(nn.Module):
    """ResNet18 + 3 deconv (SimpleBaseline): anh 256x256 -> 21 heatmap 64x64."""

    def __init__(self, pretrained=True):
        super().__init__()
        r = torchvision.models.resnet18(weights="IMAGENET1K_V1" if pretrained else None)
        self.backbone = nn.Sequential(*list(r.children())[:-2])
        layers, c = [], 512
        for _ in range(3):
            layers += [nn.ConvTranspose2d(c, 256, 4, 2, 1, bias=False), nn.BatchNorm2d(256), nn.ReLU(True)]
            c = 256
        self.deconv = nn.Sequential(*layers)
        self.head = nn.Conv2d(256, NUM_KP, 1)

    def forward(self, x):
        return self.head(self.deconv(self.backbone(x)))


def decode(hm):
    """heatmap (B,K,H,W) -> toa do (B,K,2) trong he crop IN x IN, va do tin cay (B,K)."""
    B, K, H, W = hm.shape
    conf, idx = hm.view(B, K, -1).max(-1)
    x, y = (idx % W).float(), (idx // W).float()
    s = IN / W
    return torch.stack([(x + 0.5) * s - 0.5, (y + 0.5) * s - 0.5], -1), conf


@torch.no_grad()
def evaluate(net, loader, dev, thr=0.1):
    """PCK@0.1 (nguong = 0.1 * canh crop)."""
    net.eval()
    hit = tot = 0
    for img, _, valid, kp in loader:
        pred, _ = decode(net(img.to(dev)))
        d = (pred.cpu() - kp).norm(dim=-1) / IN
        hit += ((d < thr) * valid).sum().item()
        tot += valid.sum().item()
    return hit / max(tot, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out", default="hand_net.pt")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"

    tr = DataLoader(CMUHand(a.root, "manual_train", True), a.bs, shuffle=True, num_workers=4, drop_last=True)
    te = DataLoader(CMUHand(a.root, "manual_test", False), a.bs, num_workers=2)
    net = HandNet().to(dev)
    opt = torch.optim.Adam(net.parameters(), a.lr)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs)
    best = 0
    for ep in range(a.epochs):
        net.train()
        for img, hm, valid, _ in tr:
            img, hm, valid = img.to(dev), hm.to(dev), valid.to(dev)
            loss = (((net(img) - hm) ** 2).mean((2, 3)) * valid).sum() / valid.sum().clamp(min=1)
            opt.zero_grad(); loss.backward(); opt.step()
        sch.step()
        pck = evaluate(net, te, dev)
        print(f"epoch {ep + 1}/{a.epochs} loss {loss.item():.5f} PCK@0.1 {pck:.3f}")
        if pck > best:
            best = pck
            torch.save(net.state_dict(), a.out)
    print("best PCK@0.1:", best)


if __name__ == "__main__":
    main()
