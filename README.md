# K4 Track 4 Project Capstone — Vin Perception Hackathon

Trang đề bài hackathon cuối khóa Track 4 (Computer Vision & Robotics): 2 giờ build, 10 phút demo mỗi team, đề tài gắn với hệ sinh thái Vin.

- `index.html`: trang đề bài (một file, không cần build). Mở trực tiếp bằng trình duyệt.

Nội dung gồm hướng đề tài gợi ý, bốn yêu cầu của mỗi demo, bảy trụ cột Track 4, công cụ gợi ý, thang điểm, lịch trình, checklist trước demo và FAQ. Ngày giờ, địa điểm, giám khảo, giải thưởng sẽ được ban tổ chức cập nhật.

## Chạy hệ thống tích hợp

```powershell
./setup-demo.ps1
./run-demo.ps1 --mode pick --web
```

Xem `README_DEMO.md` để cài runtime, điều khiển webcam, pause/reset, ghi lượt đo
và chạy kiểm thử. Webcam → `vision.py` → controller TV1 → PyBullet trong
`simulation/`; cảnh Three.js hiển thị trạng thái vật lý thực. Có cả log JSONL/CSV.

MVP trong `HACKATHON_PLAN.md` dùng chế độ `pick`: Pose Lite + Hand Landmarker
nhận đủ vai–khuỷu–cổ tay và 21 điểm bàn tay trên cùng frame. Một tay điều khiển X–Y,
chụm để gắp hộp được tô sáng, mở trong giỏ để tự hạ/thả. Mất tracking hoặc
gián đoạn frame quá lâu sẽ PAUSED, giữ khớp và hộp; mở tay ổn định ít nhất 0,75 giây, chờ dòng `Tracking stable: tap C once to resume`
rồi nhấn C một lần để tiếp tục. C nhấn trước khi tracking ổn định không được lưu chờ. P dừng, R reset, Q thoát.

Runner độc lập cho ba phần TV1–TV3 (không cần logger TV4):

```powershell
.runtime/python/python.exe -m dev.run_control
.runtime/python/python.exe -m dev.run_vision
.runtime/python/python.exe -m dev.run_simulation --box green
```

Tải/cập nhật đủ hai model bằng `.runtime/python/python.exe -m dev.download_model`
(nếu runtime đã cài từ trước). Runner vision hiển thị webcam/landmark và in
`HandSample` chứa keypoints thô. Cần nhìn thấy cả vai, khuỷu và bàn tay đã chọn;
che riêng vai/khuỷu hoặc bàn tay đều gây PAUSED. Overlay hiển thị riêng trạng thái
pose, hand và kết quả ghép cổ tay. `--hand Left` chọn tay trái. Runner simulation dùng
chuỗi lệnh cố định, chờ phản hồi gắp/thả thật từ PyBullet rồi in PASS; thêm
`--headless` để kiểm tra không mở GUI. Chạy tích hợp với `--no-log` nếu chỉ cần
phần TV1–TV3. Đầu vào tổng hợp không thay thế kiểm thử người dùng với webcam.

Nhận diện cả vai–khuỷu–cổ tay và cho robot di chuyển theo cánh tay:

```powershell
./run-demo.ps1 --mode arm --web
```

Giữ yên cánh tay rồi nhấn **C** để hiệu chuẩn, chờ **FOLLOWING** trước khi di chuyển.
`--hand Left` chọn tay trái; **P** dừng, **C** hiệu chuẩn lại, **R** reset.

- `HACKATHON_PLAN.md`: phạm vi và tiêu chí nghiệm thu.
- `TV1_HANDOFF.md`: hợp đồng dữ liệu và module.
- `./run-demo.ps1 --demo --headless --web`: kiểm tra bằng tay tổng hợp và vật lý thật.
- `.runtime/python/python.exe -m unittest discover -s tests -v`: kiểm thử cả tích hợp.
- `python -m dev.run_control`: runner TV1 dùng stub, chỉ cần thư viện chuẩn.

## Pipeline độc lập TV2 (tham khảo)

Các runner bên dưới là bản thử nghiệm ban đầu, không thay thế `main.py`.
Huấn luyện CMU là tùy chọn ngoài MVP; cài `requirements-training.txt` nếu cần.
Windows nên dùng runtime được `setup-demo.ps1` tạo để có PyBullet dựng sẵn.

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
Huong dan chay tich hop va runtime Windows: xem `README_DEMO.md`.

### File
- `run_holistic.py`  : MediaPipe Holistic (canh tay + 21 keypoint moi ban tay) -> mo phong
- `sim_env.py`       : moi truong PyBullet, ban tay 21 khop, logic cam/nam
- `train_hand.py`    : huan luyen model tren CMU Panoptic Hand (tuy chon, can torch)
- `run_pipeline.py`  : Pose + model CMU tu train (tuy chon, can `pip install torch torchvision`)
- `requirements-holistic.txt` : chi can cho run_holistic.py
- `requirements.txt` : dependency demo; `requirements-training.txt` gom torch tuy chon

### Loi thuong gap
- `AttributeError: module 'mediapipe' has no attribute 'solutions'`: kiem tra da chay `conda activate hand-sim` va chon moi truong Conda `hand-sim` trong **Python: Select Interpreter**. Moi truong nay cai MediaPipe `0.10.14`; khong chay bang Python khac da cai MediaPipe phien ban moi.
- Webcam den/khong mo: thu `--source 1`, dong Zoom/Teams, cap quyen camera.
- Giat: chon cau hinh `Holistic nhe (complexity 0)`.
- Tay trong sim bi lat/nguoc: doi dau trong `to_sim()` o `sim_env.py`.
