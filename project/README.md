# Arm & Hand 3D → PyBullet

Nhận diện cánh tay + bàn tay trong không gian 3D qua **một webcam** (MediaPipe Tasks API)
và tái hiện theo thời gian thực trong môi trường mô phỏng **PyBullet**.
Phạm vi: chỉ nhận diện và đưa vào mô phỏng (chưa có robot / nhiệm vụ gắp đồ).

```
webcam ──► [luồng perception] PoseLandmarker + HandLandmarker
                 │  ghép vai→khuỷu→cổ tay→21 điểm bàn tay, đổi gốc về vai, One Euro Filter
                 ▼
          LatestBuffer (thread-safe, chỉ giữ frame mới nhất)
                 ▼
          [luồng chính] PyBullet (mô hình tay kinematic + bàn + hộp)  /  matplotlib 3D  /  console
```

## Cài đặt

Yêu cầu Python 3.10 hoặc 3.11, chạy được trên CPU (không cần GPU).

**Windows (khuyên dùng conda):** PyPI không có wheel PyBullet cho Windows, `pip install pybullet`
sẽ phải build từ source (cần Microsoft C++ Build Tools). Cách đơn giản là dùng
[Miniforge](https://github.com/conda-forge/miniforge) và bản PyBullet build sẵn của conda-forge:

```bash
cd project
conda env create -f environment.yml
conda activate armsim
```

> Luôn `conda activate armsim` (hoặc `conda run -n armsim python main.py ...`) trước khi chạy.
> Gọi thẳng `...\envs\armsim\python.exe` khi chưa activate sẽ thiếu đường dẫn DLL và
> MediaPipe có thể crash (mã thoát 0xC06D007F).

**Linux / macOS (hoặc Windows đã có C++ Build Tools):**

```bash
cd project
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Các file model `.task` của MediaPipe được **tự tải** vào `models/` ở lần chạy đầu
(`pose_landmarker_full.task`, `hand_landmarker.task`).

Kiểm thử logic (không cần webcam): `python tests/test_core.py`.

## Cách chạy

| Lệnh | Chức năng |
|---|---|
| `python main.py` | Webcam → PyBullet real-time (mốc 3) |
| `python main.py --debug-3d` | Chỉ perception + bộ xương 3D bằng matplotlib, không mở PyBullet |
| `python main.py --print` | In tọa độ 3D từng điểm ra console (làm tròn 3 chữ số) |
| `python main.py --record clip.npz` | Chạy bình thường và ghi chuỗi frame 3D ra file (lưu khi thoát) |
| `python main.py --replay clip.npz` | Phát lại file vào PyBullet, không cần webcam (`--no-loop` để chạy 1 lần) |
| `python main.py --replay clip.npz --debug-3d` | Phát lại vào matplotlib |
| `python -m tools.record_replay --synthetic demo.npz` | Sinh dữ liệu giả (với tay, chạm bàn, nắm/mở, có 1.5 s mất dấu) |
| `python -m tools.record_replay --info clip.npz` | Xem thông tin file ghi |

Tuỳ chọn khác: `--hands left|right|both` (ghi đè config), `--print --sim` (in tọa độ và vẫn mở
PyBullet), `--duration 10` (tự thoát), `--headless` (PyBullet DIRECT), `--screenshot scene.png`.

**Phím tắt** — cửa sổ webcam: `q`/`ESC` thoát. Cửa sổ PyBullet: `r` đặt lại khối hộp,
`c` đo lại độ dài xương, `q`/`ESC` thoát.

Mọi tham số (camera id, độ phân giải, tay nào, tham số filter, scale, vị trí gốc, bàn, hộp,
camera mô phỏng) nằm trong [config.yaml](config.yaml).

## Cấu trúc

```
main.py                 điểm vào, vòng lặp chính, chọn chế độ
config.yaml             toàn bộ tham số
perception/
  landmarker.py         bọc PoseLandmarker + HandLandmarker (chế độ VIDEO), tự tải model
  fusion.py             ArmHandFrame, ghép pose+hand, đổi gốc, lọc, xử lý mất dấu
  filters.py            One Euro Filter (tự cài đặt, vector hoá)
  pipeline.py           luồng perception, LatestBuffer, vẽ overlay webcam
sim/
  transforms.py         ma trận chuyển trục MediaPipe → PyBullet, quaternion
  arm_model.py          mô hình tay: cầu ở khớp + capsule ở xương, body kinematic có collision
  world.py              mặt đất, bàn, hộp, camera, text debug, ArmScene
tools/
  debug_3d.py           hiển thị bộ xương bằng matplotlib 3D
  record_replay.py      ghi/phát lại .npz, sinh dữ liệu giả
```

## Hệ tọa độ

**Đầu ra perception** (`ArmHandFrame`: `timestamp, shoulder, elbow, wrist, hand(21,3), confidence, valid`)
dùng hệ trục MediaPipe, đơn vị **mét**, gốc tại **vai** của tay được theo dõi
(chế độ `both`: gốc tại trung điểm hai vai để hai tay không chồng lên nhau):

- `x` sang phải ảnh (= bên trái người), `y` xuống dưới, `z` ra xa camera (= ra sau lưng).

Cách ghép bộ xương:
1. Pose (`pose_world_landmarks`, gốc ở hông) cho vai/khuỷu/cổ tay.
2. Hand (`hand_world_landmarks`, gốc quanh tâm bàn tay) cho 21 điểm; tịnh tiến để điểm 0
   của bàn tay trùng cổ tay của pose. Bàn tay được ghép với cổ tay pose gần nhất trên ảnh 2D
   (nhãn handedness chỉ dùng để phân xử).
3. Trừ vị trí vai → chuyển động không phụ thuộc vị trí đứng.

**Lật gương:** ảnh đưa vào model luôn là ảnh *không lật* để hình học 3D giữ đúng chiều
(tay phải vẫn là tay phải). HandLandmarker gán nhãn Left/Right với giả định ảnh selfie đã lật,
nên nhãn được đảo lại. Cửa sổ webcam chỉ lật khi *hiển thị* (`display.mirror`). Nếu webcam của
bạn tự lật gương ở driver, đặt `camera.source_mirrored: true`.

**Mô phỏng PyBullet** (Z hướng lên, người nhìn theo +X):

```
            x_mp  y_mp  z_mp
    x_sim [  0     0    -1 ]    trước mặt  = về phía camera
    y_sim [  1     0     0 ]    bên trái người
    z_sim [  0    -1     0 ]    hướng lên
```

`p_sim = origin + scale · R · p_mp`, với `origin = sim.origin` (mặc định `(0, 0, 1.4)`).
`det(R) = +1` nên đây là phép quay thuần, không phản chiếu. Camera mô phỏng mặc định
nhìn từ sau lưng, nên mô hình chuyển động giống như bạn soi gương. Hệ trục nhỏ tại vai:
đỏ = X, xanh lá = Y, xanh dương = Z.

## Mô hình trong mô phỏng

- Hình cầu ở vai, khuỷu, cổ tay và 20 điểm bàn tay còn lại; capsule cho cánh tay trên,
  cẳng tay và 21 đốt theo kết nối chuẩn MediaPipe Hands. Màu: cánh tay xanh dương
  (tay trái xanh ngọc), lòng bàn tay kem, cái đỏ, trỏ cam, giữa vàng, áp út xanh lá, út tím.
- Mỗi phần là body khối lượng 0 có collision shape, cập nhật bằng
  `resetBasePositionAndOrientation` (quaternion quay trục Z của capsule về vector giữa hai khớp).
  Các khối hộp trên bàn là vật thể động nên có thể bị tay đẩy.
- PyBullet không đổi được kích thước shape, nên độ dài xương được đo (median) từ
  `sim.calib_frames` frame hợp lệ đầu tiên rồi dựng lại; nhấn `c` để đo lại.
- Mất tay hoặc mất pose: giữ giá trị cuối tối đa `perception.hold_time` (0.5 s), sau đó
  `valid=False`, mô hình đứng yên và chuyển màu xám.
- Text debug trong cảnh: FPS perception, trạng thái valid, tọa độ cổ tay và đầu ngón trỏ
  (hệ sim, tương đối vai, mét).

## Hạn chế

- **Độ sâu từ một webcam chỉ là ước lượng** của mạng nơ-ron (world landmarks), không phải đo
  thật. Sai số theo trục trước-sau (hướng về camera) lớn hơn nhiều so với hai trục còn lại,
  có thể vài cm đến hơn 10 cm; độ dài xương có thể dao động.
- Hướng bàn tay so với cẳng tay dựa trên hai model độc lập nên đôi khi lệch nhẹ ở cổ tay.
- Body kinematic được "dịch chuyển tức thời" mỗi frame: chuyển động rất nhanh có thể xuyên
  qua vật nhỏ, và lực đẩy lên vật đến từ cơ chế giải đâm xuyên chứ không từ vận tốc thật.
- Trên CPU, model `full` + hand thường đạt khoảng 15–30 FPS tuỳ máy; dùng
  `perception.pose_model: lite` hoặc giảm độ phân giải nếu chậm.

## Mẹo để nhận diện tốt

- Ánh sáng tốt, đều, tránh ngược sáng (cửa sổ sau lưng).
- Đứng/ngồi cách camera **1–2 m**, để **cả vai** (và tốt nhất cả nửa thân trên) lọt khung hình.
- Mặc **áo tay ngắn** hoặc xắn tay áo để khuỷu và cổ tay rõ ràng.
- Phông nền đơn giản, không có người khác trong khung hình.
- Giữ tay yên ~1 giây lúc đầu để bước đo độ dài xương lấy được số liệu ổn định.
