# K4 Track 4 Project Capstone — Vin Perception Hackathon

Trang đề bài hackathon cuối khóa Track 4 (Computer Vision & Robotics): 2 giờ build, 10 phút demo mỗi team, đề tài gắn với hệ sinh thái Vin.

- `index.html`: trang đề bài (một file, không cần build). Mở trực tiếp bằng trình duyệt.

Nội dung gồm hướng đề tài gợi ý, bốn yêu cầu của mỗi demo, bảy trụ cột Track 4, công cụ gợi ý, thang điểm, lịch trình, checklist trước demo và FAQ. Ngày giờ, địa điểm, giám khảo, giải thưởng sẽ được ban tổ chức cập nhật.

## Triển khai hệ thống

- `HACKATHON_PLAN.md`: phạm vi MVP, phân công, kiến trúc và tiêu chí nghiệm thu.
- `TV1_HANDOFF.md`: giao diện tích hợp, hướng dẫn chạy và giới hạn kiểm chứng phần TV1.
- `contracts.py`, `config.py`, `control.py`, `main.py`: hợp đồng, cấu hình, điều khiển và vòng lặp tích hợp.

Chạy độc lập phần TV1 bằng Python 3.11, không cần dependency ngoài:

```powershell
.venv/Scripts/python.exe -m dev.run_control
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Runner dùng dữ liệu tổng hợp. Chạy `main.py` với webcam/robot thật cần module
`vision.py` của TV2 và `simulation.py` của TV3 theo giao diện trong tài liệu bàn giao.

## TV2 — Pipeline tracking độc lập

Nhánh `huyenlili-feat` bổ sung `run_holistic.py` (MediaPipe Holistic),
`sim_env.py` (mô phỏng bàn tay PyBullet), và pipeline huấn luyện/suy luận CMU tùy chọn.
Đây là luồng chạy riêng; chưa có `vision.py` với `Vision(config)`, `latest_sample()`
và đầu ra `HandSample` theo hợp đồng TV1. Chưa tích hợp với `main.py` hoặc mô phỏng
Three.js trong `simulation/`. Phần huấn luyện là thử nghiệm ngoài phạm vi MVP
trong `HACKATHON_PLAN.md`.

Để hoàn tất bàn giao TV2 cần bổ sung một tay được chọn, tọa độ tâm lòng bàn tay
trên ảnh gương, pinch ratio theo pixel, timestamp monotonic, mẫu invalid khi mất
tracking, overlay và vòng đời start/close theo `TV1_HANDOFF.md`.
`run_holistic.py --sim` giữ dữ liệu cử chỉ cũ khi mất landmark tay và vẫn cập nhật
mô phỏng theo pose; chưa đáp ứng cơ chế PAUSED của controller TV1.

Các hướng dẫn dưới đây dành cho pipeline độc lập do TV2 bàn giao.

### Chay nhanh trong VS Code
1. Trong VS Code, **File -> Open Folder** chon thu muc goc cua repo nay.
2. Mo terminal Conda va tao moi truong Python 3.11:
   ```powershell
   conda create -n hand-sim python=3.11 pip -y
   conda activate hand-sim
   python -m pip install -r requirements-holistic.txt
   ```
3. `Ctrl+Shift+P` -> **Python: Select Interpreter** -> chon moi truong Conda `hand-sim`.
4. Nhan **F5** -> chon `Holistic + Sim (webcam)`. Nhan **Esc** tren cua so video de thoat.

Hoac chay tu terminal sau khi `conda activate hand-sim`:
```powershell
python run_holistic.py --sim
```
`setup.bat` va `setup.sh` van co the dung neu muon tao moi truong `.venv` thay vi Conda.

### File
- `run_holistic.py`  : MediaPipe Holistic (canh tay + 21 keypoint moi ban tay) -> mo phong
- `sim_env.py`       : moi truong PyBullet, ban tay 21 khop, logic cam/nam
- `train_hand.py`    : huan luyen model tren CMU Panoptic Hand (tuy chon, can torch)
- `run_pipeline.py`  : Pose + model CMU tu train (tuy chon, can `pip install torch torchvision`)
- `requirements-holistic.txt` : chi can cho run_holistic.py
- `requirements.txt` : day du, gom torch (cho train_hand / run_pipeline)

### Loi thuong gap
- `AttributeError: module 'mediapipe' has no attribute 'solutions'`: kiem tra da chay `conda activate hand-sim` va chon moi truong Conda `hand-sim` trong **Python: Select Interpreter**. Moi truong nay cai MediaPipe `0.10.14`; khong chay bang Python khac da cai MediaPipe phien ban moi.
- Webcam den/khong mo: thu `--source 1`, dong Zoom/Teams, cap quyen camera.
- Giat: chon cau hinh `Holistic nhe (complexity 0)`.
- Tay trong sim bi lat/nguoc: doi dau trong `to_sim()` o `sim_env.py`.
