# Bàn giao TV1 — Tích hợp và điều khiển

## Trạng thái

### Đối chiếu kế hoạch — phạm vi TV1–TV3

- `pick` là chế độ MVP mặc định. Nhánh `arm` là thử nghiệm tùy chọn, không cần
  cho chu trình gắp–thả trong kế hoạch.
- Pause gửi `hold_position=True`; simulator chốt góc khớp tại lần dừng đầu tiên
  và giữ các góc đó đến khi tiếp tục/reset, không giải IK lại khi đang dừng.
- Khoảng trống frame hoặc vòng điều khiển vượt `sample_max_age_s` cũng gây pause,
  kể cả khi mẫu mới nhất vừa đến còn mới. Không dùng khoảng trống đó làm bằng
  chứng tay mở/chụm ổn định. Phục hồi cần tracking và tay mở liên tục
  `resume_stable_s=0.75` giây; khi hiện `Tracking stable: tap C once to resume`
  mới nhận C. Phím C nhấn sớm không được xếp chờ; mất tracking hủy xác nhận.
  Overlay ghi lý do pause và tuổi/thời gian xử lý frame; terminal cũng in sự kiện
  paused/resumed khi chạy `--no-log`.
- Vision không phụ thuộc pipeline Holistic cũ để vẽ landmark. Thiếu điểm,
  landmark không hữu hạn hoặc ra ngoài ảnh trả mẫu invalid. Ngưỡng kích thước
  lòng bàn tay nằm trong `Config.hand_min_palm_px`.
- Cảnh PyBullet có mặt bàn Z=0, trạm băng chuyền dừng, Panda, ba hộp và giỏ.
  Chỉ hộp từng được gắp rồi release mới đủ điều kiện xác nhận placed.
- Đã bổ sung `python -m dev.run_vision` (webcam hoặc `--source video.avi`) và
  `python -m dev.run_simulation --box green` (chuỗi lệnh vật lý thật;
  `--headless` chạy nhanh không GUI). Các runner tự đóng tài nguyên khi lỗi/thoát.
- Phần TV4, lượt đo người dùng và video dự phòng không thuộc đợt sửa này.

Đã triển khai phần TV1 độc lập với camera và thư viện robot. `contracts.py`,
`config.py` là giao diện dùng chung; thay đổi hai file này cần thống nhất với TV1.
Phần tích hợp hiện có `vision.py`, package `simulation/` và `metrics.py` theo
giao diện bên dưới. Xem `README_DEMO.md` để thiết lập runtime và chạy hệ thống
đã ghép. Các runner TV1 vẫn giữ vai trò kiểm thử bằng dữ liệu tổng hợp.

## Chạy ngay

Python 3.11; phần TV1 chỉ cần thư viện chuẩn, không cần cài thêm dependency.
Tại thư mục gốc, dùng Python của môi trường dự án:

```powershell
.venv/Scripts/python.exe -m dev.run_control
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe main.py --help
```

Runner tạo mẫu tay mở → chụm ở hộp `green` → di chuyển đến giỏ → mở.
Đầu ra gồm thời điểm chuyển trạng thái, sự kiện và kết quả `PASS`, một attach,
một release. `LocalSimulation` chỉ theo setpoint tức thời, không tính vật lý/IK.
Dữ liệu này không đưa vào `results/` và không phải kết quả 10 lượt đánh giá thật.
Stub nằm trong runner của TV1, không chiếm file `dev/fakes.py` của TV4.

## Quy ước chung

- Tất cả timestamp dùng `time.monotonic()`, đơn vị giây, cùng tiến trình/miền đồng hồ.
- `HandSample` chứa `arm_side`, `arm_keypoints` (shoulder/elbow/wrist),
  `hand_keypoints` (21 điểm), `pose_valid`, `hand_valid`, `image_width/height`.
  Điểm cánh tay là `(x, y, z, visibility, presence)`; bàn tay là `(x, y, z)`.
  Tất cả x/y trên cùng ảnh **đã lật gương**, chuẩn hóa [0,1]. Z chỉ là dữ liệu
  model, không điều khiển độ cao robot. Không ghép world coordinates hai model.
- `vision.py` chạy Pose Lite + Hand Landmarker trên cùng frame/timestamp, ghép
  cổ tay theo khoảng cách pixel và giữ cố định bên đã chọn. Trên ảnh gương,
  tay phải của người dùng tương ứng Pose 11/13/15; tay trái tương ứng Pose
  12/14/16. Chọn bàn tay bằng khoảng cách tới cổ tay Pose đã chọn, không lọc
  bằng nhãn handedness của model Hands vì nhãn có thể lệch với Pose trên ảnh
  gương. Không có bàn tay đủ gần thì trả invalid, không chuyển sang tay còn lại.
- `control.extract_hand_features()` là nơi duy nhất tính tâm lòng bàn tay và
  `pinch_ratio` từ keypoints, sửa tỉ lệ theo kích thước ảnh; controller kiểm tra
  lại đầy đủ dữ liệu, visibility/presence, bên tay và khoảng cách ghép cổ tay.
  Không nhận định dạng `HandSample(u, v, pinch_ratio)` cũ. Các runner và fixture
  đã chuyển sang keypoints thô; `dev.hand_samples` chỉ tạo dữ liệu tổng hợp.
- Rect điều khiển: `(left, top, right, bottom)` trong `config.image_rect`.
  Ảnh sang phải → X tăng; ảnh lên trên → Y tăng. Ngoài rect thì clamp.
  Dưới `pinch_close` là chụm, trên `pinch_open` là mở; khoảng giữa không tạo
  bằng chứng xác nhận mới. Các ngưỡng tính/ghép tay nằm trong `config.py`.
- Chế độ pick dùng hai ngưỡng chất lượng pose trong `config.py`:
  `pick_pose_acquire=0.55` để bắt đầu và `pick_pose_retain=0.40` để duy trì.
  Cả visibility và presence của vai/khuỷu/cổ tay phải đạt ngưỡng trên frame hiện
  tại. Mất điểm, ra ngoài ảnh, chất lượng dưới ngưỡng duy trì hoặc gián đoạn
  frame sẽ yêu cầu bắt lại; không tái sử dụng tọa độ khuỷu cũ. Chế độ arm vẫn
  dùng `arm_visibility` riêng. Overlay hiển thị v/p từng khớp và khớp yếu nhất.
- `frame_id` tăng dần; frame lặp không được tính thêm thời gian xác nhận cử chỉ.
  Mẫu sai, lỗi thời hoặc timestamp đi lùi làm controller pause.
- Vị trí robot tính bằng mét, trong hệ tọa độ simulator. `target_reached` phải
  dựa trên vị trí EE thực; controller còn kiểm tra khoảng cách đến setpoint.
- ID hộp là chuỗi `red`, `green`, `blue`, không phải body ID nội bộ PyBullet.
  `placed_box_ids` là tập ID được simulator xác nhận sau khi thả và ổn định.
- Tất cả thao tác simulator, GUI và reset chạy trên luồng gọi `main.run`.
  Vision callback chỉ ghi đè mẫu/overlay mới nhất, không gọi simulator.

## Giao diện TV2

`vision.py` xuất class `Vision(config)`:

```python
start()                         # bắt đầu camera/worker
latest_sample() -> HandSample | None
close()                         # giải phóng camera/worker, kể cả start lỗi
latest_overlay()                # tùy chọn: BGR ndarray hoặc None, không block
poll_key()                      # tùy chọn: 'p', 'c', 'r', 'q' hoặc None
```

`main.py` hiển thị bản copy overlay bằng OpenCV nếu có `latest_overlay()`;
TV2 vẽ landmark và rect; main vẽ con trỏ từ kết quả trích keypoints của TV1. Main bổ sung trạng thái controller,
hộp nhắm tới, hộp đang giữ và bộ đếm từ simulator. OpenCV chỉ import khi có ảnh.
TV2 không tự xác nhận cử chỉ theo thời gian: TV1 sở hữu logic này.

## Giao diện TV3

Package `simulation/` xuất class `Simulation(config)`:

```python
initialize() -> SimStatus | None
step(command: RobotCommand, dt: float) -> SimStatus
try_attach(box_id: str) -> bool
release()
reset() -> SimStatus | None
close()
```

Nếu initialize/reset không trả trạng thái, main gọi `step(home_command, 0.0)`
để đọc trạng thái. `dt=0` phải đọc được feedback mà không tiến thời gian vật lý.
`step` chỉ điều khiển chuyển động và hình dạng gripper; **không thực thi action**.
Main gọi `try_attach`/`release` sau step đúng một lần theo `command.action`.
Feedback ở tick sau xác nhận kết quả, không dùng bool của `try_attach` để suy ra đã gắp.

TV3 cần kiểm tra khoảng cách thực giữa điểm gắp và hộp, tính hợp lệ của ID,
chưa nằm trong giỏ và chưa có liên kết; attach lặp cùng hộp phải idempotent.
`candidate_box_id` dùng hình học thực để tô sáng hộp hợp lệ dưới đầu gắp;
khi đã chọn hộp, controller giữ nguyên ID cho cả chu trình hạ/gắp.
Release/reset phải dọn liên kết; chỉ ghi nhận placed khi hộp nằm trong giỏ và ổn định.

**Cấu hình mặc định đã qua kiểm tra IK với Panda đi kèm PyBullet.** Khi đổi robot,
cần kiểm chứng lại workspace, home, pose hướng xuống và độ cao EE.
Các giá trị Z là gốc link EE, không phải đáy ngón kẹp. Khoảng cách attach đo tại
điểm gắp đã bù tool offset; TV3 cần chốt transform này với TV1 trước tích hợp.
Không so trực tiếp khoảng cách tâm hộp tới gốc EE khi tool có độ lệch.

## Giao diện TV4

Nếu muốn ghép logger vào main, `metrics.py` xuất `Metrics(config)` với
`record_event(event: dict)` và `close()` tùy chọn. Dữ liệu event đúng trường của
`contracts.Event`, timestamp monotonic. Có thể dùng adapter nếu logger có API khác.

Các sự kiện gồm `session_started`, `session_ended`, `reset`, `state_changed`,
`attach_requested`, `picked`, `pick_rejected`, `pick_failed`, `place_rejected`,
`release_requested`, `placed`, `place_failed`, `carry_failed`, `paused`, `resumed`.
`placed` chỉ phát một lần cho mỗi ID cho đến reset. Feedback `placed_box_ids`
vẫn là nguồn bộ đếm. Lệnh attach/release không phải bằng chứng thành công.

TV4 sở hữu bắt đầu/kết thúc lượt thử, timeout 30 giây và `save_trial(TrialRecord)`.
Controller không biết operator/hộp yêu cầu nên event `trial_id` để trống;
logger/điều phối lượt thử gắn ngữ cảnh lượt đang chạy. Không cần đọc biến riêng
của controller. Reset giữa lượt phải được ghi là lượt gián đoạn, không bỏ kết quả.

## Ghép module thật

```powershell
.venv/Scripts/python.exe main.py
.venv/Scripts/python.exe main.py --metrics-module metrics
.venv/Scripts/python.exe main.py --no-overlay --duration 60
```

Mặc định main nạp `Vision` từ `vision` và `Simulation` từ `simulation`.
Có thể chọn module khác bằng `--vision-module` / `--simulation-module`, hoặc
gọi trực tiếp `main.run(vision, simulation, metrics)` với instance/adapter.
Chưa có module thật thì CLI báo rõ module thiếu và lệnh chạy runner độc lập.

Phím: **P** pause, **C** xác nhận tiếp tục, **R** reset cả simulator/controller,
**Q** hoặc Escape thoát. Nếu tắt overlay, dùng `vision.poll_key()` cho các phím
hoặc Ctrl+C để thoát. Cleanup camera, simulator và logger nằm trong `finally`.

## Hành vi và giới hạn

- Khởi động phải có tay mở ổn định trước khi nhận cạnh chụm để gắp.
- Tọa độ được lọc theo thời gian và giới hạn tốc độ cả XYZ. Mỗi tick có dt tối đa
  để tránh nhảy mục tiêu sau khi vòng lặp bị chậm.
- Mất tay: giữ vị trí EE thực, giữ hộp, hủy mục tiêu cũ. Phục hồi cần tay mở ổn định
  và C; hệ thống nâng tại XY hiện tại trước, rồi mới điều khiển ngang.
  Chu trình hạ bị gián đoạn sẽ không tự chạy lại.
- Mở tay ngoài giỏ giữ nguyên hộp; cần đưa vào giỏ rồi chụm/mở lại để đặt.
- Attach không xác nhận: nâng về an toàn; không tự retry khi vẫn giữ cử chỉ chụm.
  Chuyển động quá hạn hoặc release không xác nhận: pause, cho phép reset.
- Chưa có tránh va chạm. Làm mượt và pause không giải quyết mọi lỗi nhận cử chỉ.
  Tính đúng đắn vật lý, tải trọng, camera và trải nghiệm thật cần TV2/TV3/TV4 kiểm chứng.

## Kiểm chứng phần TV1

Bộ kiểm thử kiểm tra chu trình gắp/thả, tốc độ, hướng mapping và clamp,
chụm lúc khởi động, gắp xa hộp, attach thất bại, phân biệt lệnh/feedback,
thả ngoài giỏ, placement thất bại, mất tay khi giữ hộp, phục hồi có xác nhận,
frame lỗi/lặp/cũ, timeout, reset giữa chu trình, điều phối và cleanup khi camera lỗi.
Không thay thế bảy kiểm tra tích hợp bắt buộc trên máy demo trong HACKATHON_PLAN.md.

## Tích hợp nhánh TV4 vào main

Đã bổ sung công cụ của `feat/thanh-vien-4`: `dev.fakes`, `dev.run_metrics`,
fixtures, logger độc lập và báo cáo. Fake dùng `HandSample` keypoints thô hiện tại;
API `Metrics(config)` của ứng dụng được giữ bên cạnh `MetricsLogger` của TV4.
CSV trial từ ứng dụng có thể nhập thẳng bằng runner TV4. Dependency tích hợp vẫn
đi qua `requirements-demo.txt`; snapshot Linux TV4 được giữ để tham khảo.

Kiểm tra độc lập: `python -m dev.run_metrics --self-check` và
`python -m dev.run_metrics`. Lệnh thứ hai chỉ tạo kết quả mẫu trong thư mục tạm.
