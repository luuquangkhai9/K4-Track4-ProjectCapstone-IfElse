# Demo robot gắp hàng bằng cử chỉ — bàn giao TV4

Phạm vi TV4: fake, dữ liệu mẫu, log/CSV, báo cáo, môi trường tích hợp và chuẩn bị demo. Không triển khai/sửa `contracts.py`, `config.py`, `main.py`, `control.py`, `vision.py`, `simulation.py`, `models/` hoặc `assets/` của TV1–TV3.

## Chạy ngay, không cần webcam hoặc robot

Từ thư mục gốc repository, Python 3.11:

```bash
python -m dev.run_metrics
python -m dev.run_metrics --self-check
```

Lệnh đầu kiểm tra dữ liệu mẫu theo đáp án rồi tạo CSV, metadata và báo cáo ở thư mục `/tmp/ifelse-tv4-synthetic-...` (trên hệ điều hành khác: thư mục tạm tương ứng). Không cần cài dependency để chạy hai lệnh này. Chạy dưới dạng `python -m ...`, không chạy trực tiếp file trong `dev/`.

Đáp án **mẫu**, chưa phải thành tích demo: 10 lượt, 8 thành công, 1 gắp nhầm, 1 reset khi mất tracking, trung vị 22 giây trên 8 lượt thành công. Hai người thao tác trong mẫu cũng là nhãn tổng hợp. Fixtures nằm trong `dev/sample_data/`, không đưa chúng vào `results/`.

## Môi trường tích hợp

Đã kiểm chứng cài đặt, import và PyBullet DIRECT trong venv CPython 3.11.7 trên WSL2 Linux; xem `results/environment/validation.md`. Webcam, model và GUI còn chờ thử trên đúng máy demo.

Chọn CPython 3.11 64-bit. Không cài vào Python hệ thống/Conda dùng chung. Ví dụ Linux:

```bash
python3.11 -m venv /tmp/ifelse-demo-venv
source /tmp/ifelse-demo-venv/bin/activate
python -m pip install --only-binary=:all: -r requirements.txt
python -m pip check
python -m dev.run_metrics --check-env --check-simulation
```

Nếu máy dùng lệnh `python` cho bản 3.11 thì thay `python3.11` tương ứng. `--only-binary` giúp phát hiện sớm nền tảng không có wheel, tránh biên dịch trong giờ thi. `requirements.txt` khóa bốn dependency trực tiếp; snapshot dependency gián tiếp đã thử nằm tại `results/environment/requirements-linux-python311.txt`. Có thể dùng snapshot với `pip install -r` để tái tạo cùng môi trường Linux/Python 3.11. Không tự nâng phiên bản giữa buổi.

Chỉ dùng `opencv-contrib-python`, không cài thêm `opencv-python` hoặc các bản headless vào cùng venv. PyBullet DIRECT kiểm tra được trên máy không có màn hình; GUI, robot, IK và webcam phải được xác nhận riêng trên đúng máy demo.

TV2 sở hữu model và file `models/`. Tên bàn giao đề xuất: `models/hand_landmarker.task`, tương ứng Hand Landmarker, không dùng model Gesture Recognizer thay thế. Nguồn chính thức:

- [Hướng dẫn Hand Landmarker Python](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python)
- [Danh sách model Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models)
- [Hand Landmarker float16, bản 1](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)

Khi TV2 bàn giao model, chạy trên máy demo và đóng runner webcam khác trước:

```bash
python -m dev.run_metrics --check-env --check-simulation --check-camera --camera-index 0 --model models/hand_landmarker.task
```

Preflight mở webcam lấy một frame rồi giải phóng; tải model bằng MediaPipe Tasks; không chạy module do thành viên khác sở hữu. `--check-env` trả mã lỗi khác 0 nếu dependency, phiên bản hoặc probe được yêu cầu có lỗi. File bàn giao chưa có được in `PENDING`, không được coi là demo đã sẵn sàng.

**Lệnh ứng dụng cuối dự kiến: `python main.py`.** Chỉ xác nhận lệnh này sau khi TV1 bàn giao entry point; hiện không tạo entry point thay TV1. Các phím pause/resume/reset/quit cũng chờ TV1 chốt, không tự giả định.

## API logger để TV1 ghép

`metrics.py` chỉ dùng thư viện chuẩn. Nhận `dict`, dataclass hoặc object có thuộc tính theo hợp đồng; không đọc biến nội bộ controller/simulator. API là hai phương thức `record_event(event)` và `save_trial(trial)` của một `MetricsLogger` dùng suốt phiên.

Ví dụ tích hợp sau do **TV1 đặt vào chương trình chính**; TV4 chưa sửa file của TV1:

```python
from time import monotonic
from metrics import MetricsLogger, write_report

# Dùng đường dẫn MỚI mỗi phiên; revision phải xác định đúng bản đang đo.
logger = MetricsLogger(
    "results/build-id-session-01", data_kind="real", revision="measured-build-id"
)
started_at = monotonic()  # tại tín hiệu bắt đầu lượt, không phải lúc mở chương trình
logger.record_event({
    "timestamp": started_at, "event_type": "TRIAL_START",
    "trial_id": "T01", "box_id": requested_box_id,
    "controller_state": "READY", "reason": "",
})

# Sau xác nhận từ simulator, hoặc lúc hết giờ / hủy / reset:
logger.save_trial({
    "trial_id": "T01", "operator": operator_name,
    "requested_box_id": requested_box_id,
    "picked_box_id": confirmed_picked_box_id,  # None nếu chưa gắp
    "placed_in_bin": confirmed_in_bin,        # xác nhận sau thả, không từ lệnh
    "duration_s": monotonic() - started_at,
    "failure_reason": failure_reason,         # rỗng nếu hoàn tất bình thường
})
write_report(logger.output_dir)
```

Tên biến trong ví dụ là các giá trị TV1 nhận từ luồng chạy thật, không phải biến do logger tự tìm. Có thể truyền thẳng `TrialRecord` từ `contracts.py` vào `save_trial`.

- Sự kiện có các trường: `timestamp,event_type,trial_id,box_id,controller_state,reason`; trường không áp dụng để rỗng. Timestamp là monotonic **giây**, cùng clock trong một tiến trình, không phải epoch/ms. Logger kiểm tra thứ tự thời gian không giảm.
- Tên event gợi ý để thống nhất với TV1: `TRIAL_START`, `ATTACH_REQUEST`, `ATTACH_CONFIRMED`, `ATTACH_FAILED`, `RELEASE_REQUEST`, `PLACEMENT_CONFIRMED`, `TRACKING_LOST`, `PAUSED`, `RESUMED`, `RESET`, `TIMEOUT`, `TRIAL_END`. Đây là đề xuất nhãn, không thay đổi hợp đồng.
- Gọi logger từ cùng luồng điều phối; callback vision không trực tiếp gọi logger/simulator. Ghi các chuyển trạng thái cần thiết, không ghi từng frame vào CSV.
- Một lượt bắt đầu từ tín hiệu bắt đầu; kết thúc bằng thành công, lỗi/hủy/reset hoặc hết 30 giây. TV1 sở hữu cơ chế kết thúc theo thời hạn; logger chỉ kiểm tra/đánh giá bản ghi, không điều khiển robot.
- Reset giữa lượt phải lưu lượt thất bại trước khi reset cảnh. Gợi ý lý do: `reset_during_tracking_loss`, `operator_abort`, `timeout`, `attach_failed`. Mất tracking rồi phục hồi và hoàn tất trong hạn có thể vẫn thành công; giữ sự kiện mất tracking để phân tích.
- ID `0` hợp lệ; `None`/rỗng biểu thị chưa gắp. ID được chuẩn hóa thành chuỗi khi ghi CSV.
- Lượt trùng ID bị từ chối; reset cảnh không reset logger. Thư mục phiên đã có không được ghi đè hay tự nối lại. Nếu chương trình hỏng, các dòng đã ghi còn trên đĩa; tạo báo cáo bằng `write_report` cho phiên đó, lần chạy mới dùng thư mục mới.
- Không ghi trial cho từng sự kiện gắp/thả. Lưu đúng một bản ghi kết thúc cho mỗi lượt, tránh đếm hai lần.

## Fake cho tích hợp độc lập

`dev/fakes.py` dùng kiểu của TV1 khi `contracts.py` đã có. Khi chưa có file đó, dùng dataclass cục bộ đúng các trường dự kiến để chạy độc lập. Không tạo `contracts.py` thay TV1. Nếu hợp đồng thật không khớp, lỗi phải được giải quyết với TV1, không âm thầm chuyển lại kiểu giả.

```python
from dev.fakes import FakeSimulator, FakeVision, hand_sample, sim_status

vision = FakeVision([
    hand_sample(frame_id=0, now=100, pinch_ratio=0.8),
    hand_sample(frame_id=1, now=100.1, pinch_ratio=0.2),
    hand_sample(frame_id=2, now=100.2, valid=False),
])
vision.start()
sample = vision.latest_sample()  # đọc nhiều lần không tiêu thụ mẫu
sample = vision.advance()        # runner chủ động chuyển mẫu/thời gian

sim = FakeSimulator([
    sim_status(candidate_box_id="box_red"),
    sim_status(held_box_id="box_red"),
    sim_status(placed_box_ids=("box_red",)),
], attach_results={"box_red": True})
initial = sim.initialize()
# TV1 gọi step(command, dt), try_attach(box_id), release(), reset(), close().
```

Mỗi `step` trả một trạng thái trong kịch bản; hết kịch bản giữ trạng thái cuối. `try_attach` mặc định thất bại nếu chưa được cấu hình. Lệnh gắp/thả chỉ được ghi vào `actions`, không tự tạo phản hồi vật lý; trạng thái giữ/thả phải được cung cấp rõ trong kịch bản. `commands` lưu các lệnh đã nhận; `reset` xóa lịch sử và đưa con trỏ về đầu kịch bản. Fake không kiểm chứng IK, workspace, lực kẹp, pause thật hoặc camera thật. Runner dùng timestamp cố định phải truyền `now` cùng miền thời gian; giữ mẫu cũ sẽ hữu ích để kiểm tra stale tracking.

## Đo 10 lượt thật

1. Ghi commit/build và kiểm tra working tree của bản được đo. Chốt cùng phiên bản trong toàn bộ bộ đo.
2. TV3 bàn giao ID thật của ba hộp. Chốt trước thứ tự hộp, ví dụ đỏ–xanh dương–xanh lá–đỏ–xanh dương / xanh lá–đỏ–xanh dương–xanh lá–đỏ, rồi đổi sang ID thật.
3. TV2 thao tác T01–T05, TV4 thao tác T06–T10; dùng tên/người thao tác thực tế trong CSV. Người thứ hai phải trực tiếp dùng hệ thống.
4. Reset cảnh giữa lượt; bắt đầu tính giờ từ tín hiệu. Ghi đủ lượt lỗi, không thay lượt đẹp hơn. Tối đa 30 giây mỗi lượt.
5. Đúng hộp + đã thả vào giỏ + ≤30 giây + không có lỗi/hủy/reset mới là thành công. Median chỉ tính trên lượt thành công và luôn ghi số mẫu n. Mục tiêu 8/10 là mục tiêu nội bộ.
6. Thử che/nghiêng tay riêng: ghi hiện tượng, timestamp, trạng thái PAUSED, hộp có bị thả không và cách phục hồi. Nếu ca lỗi nằm trong bộ 10 lượt thì vẫn giữ lượt đó. Không chỉ ghi điều hệ thống được kỳ vọng sẽ làm.
7. Khi có CSV từ phiên khác, nhập bằng lệnh dưới; `--events` có thể bỏ nếu không thu sự kiện, nhưng phải nói rõ thiếu bằng chứng diễn biến.

```bash
python -m dev.run_metrics --input /path/to/trials.csv --events /path/to/events.csv --data-kind real --revision measured-build-id --output results/unique-session
```

Báo cáo tạo `summary.json` và `summary.md`. Khi chưa đủ 10 lượt hoặc chưa đủ hai người, báo cáo ghi chưa hoàn tất. Thời gian hoàn thành lượt không phải độ trễ xử lý; không suy diễn camera-to-display từ con số này.

## Ca lỗi, video và bàn giao còn chờ

| Hạng mục | Chủ module / điều kiện | TV4 làm sau khi nhận |
|---|---|---|
| Kiểu dữ liệu, main, cấu hình và phím điều khiển | TV1 | Chạy lại self-check với contracts thật; ghép logger cùng TV1, cập nhật lệnh chạy/phím |
| Webcam, overlay, model Hand Landmarker | TV2 | Kiểm tra trên máy demo, diễn ca che/nghiêng tay |
| GUI, IK, attach/release, xác nhận giỏ, reset | TV3 | Kiểm tra 7 ca nghiệm thu trong kế hoạch trên bản tích hợp |
| 10 lượt thao tác của hai người | Bản tích hợp ổn định | Ghi thật, tổng hợp thật, ghi phiên bản |
| Video dự phòng | Webcam + simulator thật chạy cùng nhau | Quay chu trình thành công, ca lỗi và reset; phát thử file offline |

Checklist nghiệm thu: khởi động/reset; mapping đúng chiều và nằm trong workspace; chụm xa không gắp; đúng hộp; chỉ đếm sau thả vào giỏ và không đếm trùng; mất tracking giữ hộp rồi phục hồi có xác nhận; reset giữa chu trình xóa liên kết/trạng thái/bộ đếm cũ. Chỉ đánh dấu đạt sau quan sát thật.

Ghi ca lỗi theo mẫu: **build — tình huống — quan sát thực — thời điểm trong video/event — nguyên nhân có bằng chứng — cách phục hồi — giới hạn còn lại**. Chưa có quan sát thì giữ trạng thái chờ.

Video dự kiến đặt tại `results/<session>/backup-demo.mp4`; quay bằng công cụ ghi màn hình sẵn trên máy, thấy đồng thời webcam/overlay và simulator. Dành khoảng 60–90 giây: hiển thị phiên bản → reset → gắp đúng hộp → chuyển/thả vào giỏ → che tay khi đang giữ → phục hồi → reset. Kiểm tra video phát được offline. Không quay fake rồi ghi nhãn demo thật.

Trước trình bày, TV4 chốt bảng đo và ca lỗi trong `DEMO_SCRIPT.md`; hiện các ô kết quả thật còn để trống có nhãn chờ.
