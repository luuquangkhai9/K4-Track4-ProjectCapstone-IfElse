# Kiểm chứng môi trường TV4

Ngày ghi nhận: 16/10/2026. Nền tảng: WSL2 Linux x86_64, glibc 2.39, CPython 3.11.7. Môi trường riêng: `/tmp/ifelse-tv4-venv`. Base Git: `eaca37d`, thêm phần TV4 trong working tree. Đây là kết quả kiểm chứng công cụ/môi trường, **không phải kết quả 10 lượt thao tác**.

Đã thực hiện:

- Cài `requirements.txt` trong venv bằng wheel, không biên dịch thư viện.
- `python -m pip check`: không phát hiện dependency hỏng.
- `python -m dev.run_metrics --check-env --check-simulation`: đúng bốn phiên bản đã khóa; import NumPy/OpenCV/MediaPipe/PyBullet thành công; truy cập được API Hand Landmarker.
- PyBullet DIRECT: tạo vật thể có khối lượng, chạy 24 bước dưới trọng lực và kiểm tra vật rơi; kết nối được giải phóng sau probe.
- `python -m dev.run_metrics --self-check`: 9 ca kiểm tra công cụ đều đạt tại thời điểm bàn giao.
- `python -m dev.run_metrics`: CSV mẫu khớp đáp án định trước, output tạo trong `/tmp/`, ngoài `results/`.

Chưa kiểm chứng: model `.task` thực tế do TV2 bàn giao, webcam, OpenCV/PyBullet GUI trên máy demo, IK/attach/release/giỏ thật của TV3, hợp đồng thật và entry point của TV1, vận hành hai người, 10 lượt thật, ca lỗi thật, video dự phòng. Các module TV1–TV3 chưa có ở bản Git được kéo về.

Snapshot dependency trong `requirements-linux-python311.txt` là output `pip freeze` từ chính venv đã kiểm tra. Dùng để tái tạo môi trường đã thử trên cùng nền tảng:

```bash
python -m pip install --only-binary=:all: -r results/environment/requirements-linux-python311.txt
python -m pip check
python -m dev.run_metrics --check-env --check-simulation
```

Snapshot không khẳng định đã thử trên Windows/macOS hoặc các phiên bản Python khác. Lệnh gốc dùng bốn dependency trực tiếp ở `requirements.txt`; snapshot khóa thêm dependency gián tiếp để tránh thay đổi resolver trong buổi demo.
