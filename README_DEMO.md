# Demo tích hợp — điều khiển robot gắp hàng bằng tay

## Robot đi theo cánh tay

Chế độ mới nhận cả **vai–khuỷu–cổ tay**, vẽ cánh tay và landmark bàn tay trên webcam,
đồng thời điều khiển khuỷu và đầu robot trong không gian XYZ:

```powershell
./run-demo.ps1 --mode arm --web
```

`--headless` dùng cảnh web thay GUI PyBullet; `--hand Left` chọn cánh tay trái,
mặc định Right. Giữ toàn bộ cánh tay được chọn trong ảnh, tránh che khuỷu/cổ tay.

1. Đứng/ngồi để webcam thấy phần thân trên cùng vai, khuỷu, cổ tay.
2. Giữ một tư thế thoải mái, nhấn **C**. Giữ yên khoảng 0.6 giây để hiệu chuẩn.
   Nếu tay còn di chuyển, cửa sổ hiệu chuẩn bắt đầu lại.
3. Khi thấy **FOLLOWING**, nâng/hạ, đưa ngang hoặc co/duỗi cánh tay.
   Robot đi theo chuyển động tương đối của cổ tay và khuỷu so với vai.
4. **P** dừng; **C** sau pause sẽ hiệu chuẩn lại ngay tại vị trí robot đang giữ,
   nên không chạy lại mục tiêu trước khi mất tracking. **R** reset rồi hiệu chuẩn lại;
   **Q**/Escape thoát. Các nút tương ứng cũng có trong cảnh web.

`arm_vision.py` dùng MediaPipe Holistic của luồng TV2 với vòng đời worker tích hợp;
không cần tải model ngoài mới. Chỉ cánh tay được chọn điều khiển, tay còn lại được
vẽ xám. Landmark bàn tay có thể mất trong khi cánh tay vẫn được theo dõi; điều này
không làm ngắt điều khiển cánh tay nếu vai/khuỷu/cổ tay còn hợp lệ.

`arm_control.py` chuẩn hóa chiều dài cánh tay và trừ vị trí vai; dịch cả người hoặc
thay đổi tỉ lệ quan sát không trực tiếp thành lệnh dịch robot. Camera x phải → robot
Y, y lên → robot Z, z hướng về camera → robot X. Chuyển động trong ảnh gương được
đổi theo cùng quy ước này cho cả hai tay. `arm_gain` mặc định 0.55 m cho một đơn vị
chiều dài tay chuẩn hóa; chỉnh trong `config.py` để tăng/giảm độ nhạy.

Robot Panda có cấu trúc khác tay người. Bộ IK nhiều điểm dùng đích khuỷu (link 3)
và cổ tay/đầu gắp (link 11) để tìm tư thế gần nhất; **không bảo đảm sao chép mọi
góc khớp 1:1 hoặc tới chính xác đồng thời cả hai điểm**. Snapshot Three.js vẽ các
khớp thực của Panda từ PyBullet, không dựng một tư thế khuỷu riêng trong trình duyệt.
Độ sâu là ước lượng tương đối từ webcam, không phải khoảng cách đo chính xác.

Chế độ arm giới hạn workspace XYZ, bán kính với tới, tốc độ mục tiêu và tốc độ khớp.
Mất hoặc landmark quá yếu, dữ liệu cũ/sai sẽ PAUSED và giữ vị trí khớp thực. Không
tự phục hồi chuyển động. Chế độ này phục vụ theo cánh tay, không tự thực hiện chu
trình gắp/thả; chọn `--mode pick` (mặc định) để dùng chu trình gắp hàng đã có.
Nút bắt đầu lượt đo gắp được ẩn trong chế độ arm.

Kiểm tra không cần webcam bằng chuyển động cánh tay tổng hợp:

```powershell
./run-demo.ps1 --mode arm --demo --headless --web
```

Chạy với vật lý thật, đánh dấu TAY GIẢ LẬP và ghi `results/synthetic/`. Kiểm thử gồm
retarget khuỷu/cổ tay, giới hạn tốc độ, hiệu chuẩn, không điều khiển bằng chuyển động
toàn thân đơn thuần, mất tracking, suy luận Holistic thật và phản hồi robot thật.
Chất lượng bám với cánh tay người vẫn cần người vận hành thử trong điều kiện webcam.

## Cài và chạy trên Windows

Tại thư mục gốc repo, PowerShell:

```powershell
./setup-demo.ps1
./run-demo.ps1 --web
```

Setup tạo runtime riêng trong `.runtime/`, dùng Python 3.11, NumPy 1.26.4,
MediaPipe 0.10.14, OpenCV contrib 4.10.0.84 và PyBullet từ conda-forge 3.25
(metadata Python của gói này báo 3.2.5). Không cần cài compiler hoặc thay Python
hệ thống. Model pretrained chính thức được tải vào `models/hand_landmarker.task`.
`requirements-vision-lock.txt` ghi phiên bản dependency đã kiểm chứng trên máy này.
Lần đầu cần mạng; runtime, model và kết quả được bỏ qua trong Git.

Lệnh chạy mở camera và cửa sổ PyBullet, phục vụ cảnh Three.js tại
`http://127.0.0.1:8765`. Mở URL trong trình duyệt nếu muốn xem cảnh web.
Three.js/font tải từ CDN, nên phần web cần mạng. Camera và PyBullet chạy cục bộ;
ảnh webcam không được gửi lên HTTP bridge và không ghi vào log.

Chỉ dùng cảnh web và cửa sổ camera, không mở GUI PyBullet:

```powershell
./run-demo.ps1 --web --headless
```

`--source 1` đổi camera; `--source clip.mp4` đọc video; `--hand Left` chọn tay trái.
Mặc định chỉ tay phải điều khiển. Không dùng điểm handedness như độ tin cậy landmark.
Nếu không mở được camera, chương trình báo lỗi, đóng tài nguyên và ghi session_failed.

Trên Linux, dùng Python 3.11 trong venv, `python -m pip install -r requirements-demo.txt`,
`python -m dev.download_model`, rồi `python main.py --web`. Bộ kiểm chứng trong repo
đã chạy trên Windows; Linux chưa được chạy thử.

## Thao tác

1. Đưa tay đã chọn vào webcam, lòng bàn tay đủ lớn, mở ngón cái–trỏ ổn định.
   Nếu đang PAUSED lúc chờ camera/tay, nhấn **C** để xác nhận tiếp tục.
2. Di chuyển tâm lòng bàn tay trong khung chữ nhật. Ảnh đã lật gương: tay sang phải
   tăng X, lên trên tăng Y. Đầu gắp giữ hướng xuống, chỉ điều khiển ngang ở độ cao an toàn.
3. Đưa đầu gắp trên hộp được tô vàng rồi chụm cái–trỏ. Controller khóa hộp đã chọn,
   hạ, yêu cầu attach, chờ simulator xác nhận, rồi nâng.
4. Mang hộp đến giỏ và mở cái–trỏ. Hệ thống chỉ hạ/thả nếu cả vị trí thực và mục tiêu
   nằm trong vùng giỏ. Mở ngoài giỏ giữ hộp; đưa vào giỏ rồi chụm/mở lại.
5. Che/mất tay làm PAUSED: giữ vị trí thực và giữ liên kết hộp. Mở tay ổn định rồi
   nhấn **C**; robot nâng tại XY hiện tại trước khi tiếp tục di chuyển ngang.

Phím trong cửa sổ camera: **P** pause, **C** xác nhận tiếp tục, **R** reset,
**T** bắt đầu lượt đo, **Q** hoặc Escape thoát. Các nút tương ứng có trên cảnh web.
Reset xóa liên kết, đưa hộp về đầu, xóa trạng thái cử chỉ và bộ đếm mô phỏng;
lượt đo đang chạy vẫn được ghi là thất bại do reset.
`--no-overlay` ẩn camera; cần `--web` để có nút thao tác, hoặc Ctrl+C để thoát.

## Kiến trúc đã ghép

```text
camera capture -> latest frame -> MediaPipe worker -> HandSample
                                                       |
                                                       v
main thread: Controller -> RobotCommand -> PyBullet Simulation -> SimStatus
                 |                              |
                 +-> metrics JSONL/CSV           +-> HTTP snapshot -> Three.js
```

- `vision.py` chuyển kết quả Hand Landmarker sang hợp đồng TV1, dùng pixel để tính
  pinch ratio trên ảnh không vuông, timestamp monotonic, rect và landmark theo cách
  vẽ của TV2. Mỗi slot chỉ giữ frame/sample mới nhất. Không có hàng đợi frame cũ.
  Mất tay đã chọn trả invalid ngay, không dùng lại cử chỉ cũ để điều khiển.
- `simulation/__init__.py` dùng Panda của PyBullet, IK, motor và fixed constraint.
  Chỉ attach khi điểm gắp thực cách hộp đủ gần; ID không hợp lệ hoặc hộp đã đặt bị từ chối.
  Attach/release lặp không tạo liên kết trùng. Không mô phỏng lực kẹp/ma sát ngón chính xác.
- `main.py` là luồng duy nhất gọi PyBullet. HTTP/vision worker không chạm simulator.
  Main thực thi action một lần; controller chờ feedback ở tick kế tiếp.
- Cảnh Three.js của TV3 trở thành viewer ở chế độ tích hợp; vị trí hộp/đầu gắp và số
  hộp thành công đều lấy từ PyBullet. Nút demo tự động của cảnh cũ bị vô hiệu. Khi
  feedback không cập nhật, giữ hình cuối và báo STALE. Lệnh HTTP tọa độ trực tiếp
  bị từ chối trong chế độ tích hợp; chỉ controller được phát chuyển động.
- Ba hộp ở trạm dừng. Robot và hộp không va chạm với nhau: việc gắp được đơn giản
  hóa bằng fixed constraint; hộp vẫn chịu trọng lực và va chạm với sàn/giỏ/hộp khác.
  Hộp chỉ được tính placed khi toàn bộ AABB trong giỏ, ở độ cao hợp lệ và ổn định.

`config.py` dùng mét/Z-up, ngưỡng chụm .30 và mở .50; xác nhận .12 giây, tracking
ổn định .30 giây, mẫu tối đa .25 giây. Độ lệch điểm gắp là .05 m dưới link EE 11.
Workspace mặc định đã kiểm tra IK ở bốn góc và tại độ cao gắp/thả với Panda đi kèm.
Thay robot, tool hoặc bố trí cảnh cần kiểm chứng lại.

## Log và lượt đo

```powershell
./run-demo.ps1 --web --operator TV2 --trial-box green
```

Sau khi tay mở ổn định và cảnh đã reset, nhấn T hoặc nút **Bắt đầu lượt đo**.
Một lượt tại một thời điểm; lệnh T lặp không ghi đè lượt đang chạy. Thay hộp yêu cầu
và người thao tác bằng tùy chọn CLI cho phiên tương ứng. Lượt kết thúc khi đặt hộp,
quá 30 giây, reset hoặc kết thúc phiên. Các lượt thất bại vẫn có hàng CSV.

Trong `results/live/<session>/`:

- `events.jsonl`: sự kiện controller/session kèm timestamp và trial_id nếu đang đo.
- `session.json`: cấu hình, phiên bản dependency, Git revision, trạng thái dirty và loại đầu vào.
- `trials.csv`: `trial_id,operator,requested_box_id,picked_box_id,placed_in_bin,duration_s,failure_reason`.

Thành công = picked_box_id đúng yêu cầu, placed_in_bin=True, duration_s ≤ 30,
failure_reason rỗng. Hộp khác vào giỏ vẫn có placed_in_bin=True nhưng reason=wrong_box.
CSV không tự khẳng định đã đạt mục tiêu 8/10. Nhóm cần tự đo đủ 10 lượt với hai người,
giữ nguyên phiên bản và quay video/ca lỗi như kế hoạch.

## Kiểm tra tự động và đầu vào tổng hợp

```powershell
.runtime/python/python.exe -m unittest discover -s tests -v
./run-demo.ps1 --demo --headless --web
```

`--demo` dùng HandSample tổng hợp để chạy **vật lý PyBullet thật**, mặc định 14 giây.
Cảnh ghi rõ TAY GIẢ LẬP; log vào `results/synthetic/`, tách khỏi đánh giá thật.
Không gọi đây là demo webcam. Runner cũ `python -m dev.run_control` còn dùng cả
simulator stub để kiểm tra TV1 mà không cài dependency.

Kiểm chứng hiện có: toàn bộ tests qua với runtime đã cài, bao gồm gắp/thả ba hộp,
kiểm tra workspace IK, gắp xa bị từ chối, pause lúc mang hộp không rơi, reset dọn
constraint, log thành công/thất bại và HTTP snapshot/input. MediaPipe đã chạy
suy luận thật; webcam khởi động/đóng phiên được. Chưa có 10 lượt điều khiển bởi
người và chưa có video dự phòng; không suy ra tỷ lệ thành công thực tế từ tests.

## Các pipeline TV2/TV3 ban đầu

`run_holistic.py --sim`, `run_pipeline.py`, `train_hand.py`, `sim_env.py` và
`python simulation/serve.py` được giữ làm thử nghiệm độc lập. Đường chạy được
khuyến nghị cho demo tích hợp là `main.py` qua `run-demo.ps1`.
Huấn luyện CMU chỉ cần khi chủ động dùng pipeline cũ:
`python -m pip install -r requirements-training.txt` (ngoài phạm vi MVP).

## Công cụ kiểm chứng TV4 đã tích hợp

```powershell
.runtime/python/python.exe -m dev.run_metrics --self-check
.runtime/python/python.exe -m dev.run_metrics
.runtime/python/python.exe -m dev.run_metrics --check-env --check-simulation
```

Runner mặc định kiểm tra dữ liệu mẫu và tạo báo cáo trong thư mục tạm, ngoài
`results/`; các số liệu này không phải kết quả demo thật. Fake đã dùng hợp đồng
keypoints thô hiện tại. `metrics.py` cung cấp cả `Metrics` cho ứng dụng và
`MetricsLogger`, `read_trials`, `summarize`, `write_report` cho đánh giá độc lập.

Nhập CSV đã ghi từ ứng dụng để tổng hợp (thay đường dẫn và mã build thực tế):

```powershell
.runtime/python/python.exe -m dev.run_metrics --input results/live/SESSION/trials.csv --data-kind real --revision BUILD_ID
```

Kết quả đo cần có đủ 10 lượt, ít nhất hai người; giữ cả lượt thất bại/reset.
Xem `DEMO_SCRIPT.md` để chuẩn bị phần trình bày và `results/README.md` cho quy ước
lưu bằng chứng. Snapshot Linux của TV4 trong `results/environment/` là tài liệu
lịch sử, không thay thế runtime Windows của `setup-demo.ps1`.
