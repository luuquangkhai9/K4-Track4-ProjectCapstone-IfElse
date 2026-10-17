# IfElse — Điều khiển robot gắp hàng bằng cử chỉ

**Báo cáo Capstone Day 28 · Track 4: Computer Vision & Robotics · Vin Perception Hackathon**

Nhóm IfElse xây dựng hệ thống dùng webcam để nhận diện cánh tay và bàn tay, chuyển cử chỉ thành lệnh điều khiển robot Panda trong mô phỏng PyBullet. Người vận hành di chuyển tay để đưa đầu gắp tới hộp, chụm ngón cái–trỏ để gắp, đưa hộp đến giỏ và mở ngón để thả. Hệ thống hiển thị landmark và trạng thái robot, tạm dừng khi mất tracking, đồng thời ghi log để kiểm chứng.

Repository: [K4-Track4-ProjectCapstone-IfElse](https://github.com/luuquangkhai9/K4-Track4-ProjectCapstone-IfElse).

## 1. Bài toán và người dùng

**Ngữ cảnh ứng dụng:** trạm chuyển kiện trong kho/nhà máy VinFast hoặc giải pháp thao tác từ xa của Vin Robotics. Người dùng mục tiêu là nhân viên vận hành cần chỉ định và chuyển kiện giữa trạm gắp và giỏ chứa. Cử chỉ tay cung cấp cách điều khiển trực quan để thử nghiệm tương tác người–robot trước khi kết nối phần cứng.

Demo tập trung vào một người, một cánh tay điều khiển, một robot, ba hộp có ID `red`, `green`, `blue` và một giỏ. Dây chuyền dừng tại trạm gắp. Trong chế độ chính `pick`, người dùng điều khiển X–Y; chương trình tự nâng/hạ theo chu trình, giữ đầu gắp hướng xuống.

Mã nguồn còn có chế độ `arm` để robot đi theo chuyển động tương đối của cánh tay trong XYZ và cảnh Three.js phản chiếu trạng thái PyBullet. Đây là phần mở rộng so với MVP. Gắp được đơn giản hóa bằng liên kết cố định tạm thời; dự án chưa chứng minh lực kẹp, tải trọng công nghiệp hay hiệu quả vận hành trên robot thật.

## 2. Thành viên và phân công

Nhóm có **5 thành viên**, đảm nhiệm 4 nhóm công việc TV1–TV4 trong [HACKATHON_PLAN.md](HACKATHON_PLAN.md). Hai thành viên cùng phụ trách TV2; ký hiệu TV là nhóm nhiệm vụ trong kế hoạch, không phải số lượng thành viên thực tế.

| Thành viên | MSSV | Vai trò | Công việc theo phân công |
|---|---|---|---|
| **Lưu Quang Khải** | **2A202602599** | **Trưởng nhóm · TV1** | Tích hợp hệ thống; hợp đồng dữ liệu và cấu hình; ánh xạ tay → robot; làm mượt, giới hạn tốc độ, máy trạng thái và chương trình chính. Các phần chính: `main.py`, `contracts.py`, `config.py`, `control.py`, `dev/run_control.py`; phần mở rộng `arm_control.py`. |
| **Đào Thị Huyền** | **2A202602670** | **TV2 · Computer Vision** | Cùng Nguyễn Đức Đông phụ trách webcam, nhận diện vai–khuỷu–cổ tay và 21 mốc bàn tay, ghép đúng bên tay, xuất `HandSample`, overlay và runner vision. Các phần: `vision.py`, `arm_vision.py`, `models/`, `dev/run_vision.py` và pipeline thử nghiệm TV2. |
| **Nguyễn Đức Đông** | **2A202602367** | **TV2 · Computer Vision** | Cùng Đào Thị Huyền thực hiện nhóm công việc TV2: thu nhận hình ảnh, xử lý landmark, kiểm tra tracking và bàn giao dữ liệu thị giác cho bộ điều khiển. |
| **Vũ Hải Minh** | **2A202602452** | **TV3 · Robotics và mô phỏng** | Dựng cảnh dây chuyền, robot, hộp và giỏ; IK, motor, gắn/thả hộp, xác nhận đặt thành công, reset; runner mô phỏng và cảnh web. Mô phỏng tích hợp nằm trong `simulation/`. |
| **Đặng Đỉnh Đoàn** | **2A202602927** | **TV4 · Kiểm chứng và demo** | Dữ liệu mẫu, fake cho kiểm thử, logger, tổng hợp số đo, môi trường demo và tài liệu/kịch bản trình bày. Các phần: `metrics.py`, `dev/fakes.py`, `dev/run_metrics.py`, `requirements*.txt`, `results/`, `README_DEMO.md`, `DEMO_SCRIPT.md`. |

## 3. Đối chiếu yêu cầu chương trình

Báo cáo dựa trên [yêu cầu hackathon](docs/GUIDE.txt), [kế hoạch nhóm](HACKATHON_PLAN.md) và mã nguồn hiện có.

| Yêu cầu | Cách đáp ứng | Trạng thái bằng chứng |
|---|---|---|
| Chạy trên webcam/cảm biến/sim | Webcam → nhận diện → điều khiển → PyBullet, có camera overlay và cảnh 3D | Có luồng tích hợp và kiểm thử vật lý; cần thử thao tác trực tiếp trên đúng máy/phòng demo. |
| Ít nhất 2 trụ cột Track 4 | Hình học, Biểu diễn, Thời gian, Bất định, Dữ liệu và Bằng chứng | Vị trí áp dụng và lý do thiết kế ở mục 5. |
| Một số đo kiểm chứng được | Bộ kiểm thử tự động; CSV lượt thử và công cụ tổng hợp | 54/54 kiểm thử đạt trong lần rà soát. Chưa có bộ 10 lượt người dùng để công bố hiệu quả điều khiển. |
| Một ca lỗi kèm nguyên nhân | Mất/che landmark, gián đoạn frame; kiểm tra PAUSED và phục hồi | Có ca kiểm thử tái lập; cần bổ sung log/video ca lỗi webcam quan sát thực tế. |
| Dữ liệu an toàn | Thành viên tự đóng vai, log trạng thái không chứa ảnh webcam | Không dùng dữ liệu thật của bệnh nhân hoặc sinh viên; chỉ ghi hình người tham gia đã đồng ý. |
| Video dự phòng và demo 10 phút | Có tài liệu vận hành và kịch bản | Chưa có video dự phòng trong bộ bằng chứng hiện tại; phân vai ở mục 10. |
| Làm nhóm qua Git và nộp cá nhân | Một repository chung, phân công rõ TV1–TV4 | Cả 5 thành viên phải tự nộp URL repo chung trên VLearn của mình. |

## 4. Kiến trúc và nguyên lý hoạt động

```text
Webcam / video
      │
      ▼
vision.py: Pose Lite + Hand Landmarker (cùng frame)
      │ HandSample: timestamp, bên tay, vai/khuỷu/cổ tay, 21 mốc bàn tay
      ▼
control.py: kiểm tra mẫu → trích cử chỉ → mapping/lọc → máy trạng thái
      │ RobotCommand: target_xyz, gripper_closed, action, box_id
      ▼
main.py → simulation/: Panda, IK, motor, liên kết gắp/thả
      ▲       │
      └───────┘ SimStatus: vị trí thực, hộp ứng viên/đang giữ/đã đặt
              ├── metrics.py → events.jsonl, session.json, trials.csv
              └── HTTP snapshot → cảnh Three.js
```

`main.py` sở hữu vòng điều phối và mọi lời gọi PyBullet. Luồng camera/vision giữ frame và mẫu mới nhất để tránh tích lũy dữ liệu cũ; luồng HTTP phục vụ hiển thị và nút thao tác. Cảnh web lấy trạng thái robot/hộp từ mô phỏng vật lý.

Trong `pick`, vision chọn cố định tay phải hoặc trái, kiểm tra pose và bàn tay trên cùng frame, đối chiếu cổ tay để tránh ghép nhầm. Controller tính tâm lòng bàn tay và tỷ lệ chụm bằng khoảng cách đầu ngón cái–trỏ chia cho kích thước lòng bàn tay. Khoảng cách được tính theo pixel để xử lý đúng ảnh không vuông.

```text
READY → LOWERING_PICK → LIFTING → CARRYING
      → LOWERING_PLACE → RELEASING → READY

Mất tracking / mẫu quá cũ / nhấn P → PAUSED
```

Controller chỉ bắt đầu gắp khi có hộp ứng viên, khóa ID hộp rồi hạ đầu gắp. Simulator kiểm tra khoảng cách thực trước khi gắn hộp; controller chờ `held_box_id` để xác nhận. Mở tay ngoài giỏ giữ nguyên hộp và yêu cầu đưa tới giỏ. Chỉ tính đặt thành công khi hộp đã thả, toàn bộ AABB của hộp nằm trong giỏ ở độ cao hợp lệ và ổn định; phát lệnh `RELEASE` chưa đủ để tính thành công.

## 5. Kiến thức Track 4 được vận dụng

| Trụ cột | Vị trí trong mã nguồn | Cách áp dụng và lý do lựa chọn |
|---|---|---|
| **Học** | `vision.py`, `models/` | Pose Lite và Hand Landmarker pretrained trích landmark. Tận dụng model sẵn có để tập trung thời gian hackathon vào tích hợp và kiểm chứng; luồng chính không cần huấn luyện từ đầu. |
| **Hình học** | `control.py`, `simulation/`, `config.py` | Ánh xạ vùng ảnh sang mặt bàn X–Y; IK chuyển đích đầu gắp thành góc khớp. Z theo chu trình giúp tránh coi độ sâu webcam đơn là khoảng cách tuyệt đối. |
| **Biểu diễn** | `contracts.py`, `control.py` | `HandSample`, `RobotCommand`, `SimStatus` tách dữ liệu cảm nhận, lệnh và phản hồi. Máy trạng thái làm rõ điều kiện gắp, mang, thả và tạm dừng. |
| **Bất định** | `vision.py`, `control.py` | Kiểm tra visibility, bên tay, ghép cổ tay, kích thước lòng bàn tay và dữ liệu sai. Hai ngưỡng chụm/mở cùng thời gian xác nhận hạn chế rung cử chỉ; mất tracking dẫn tới PAUSED. |
| **Thời gian** | `main.py`, `control.py` | Timestamp monotonic, loại mẫu cũ, làm mượt và giới hạn tốc độ. Giữ mẫu mới nhất phù hợp điều khiển tương tác, tránh hàng đợi frame tồn đọng. |
| **Dữ liệu và Bằng chứng** | `metrics.py`, `dev/run_metrics.py`, `tests/` | Lưu sự kiện, cả lượt thành công/thất bại và thông tin phiên bản. Tách dữ liệu tổng hợp khỏi dữ liệu camera để kiểm tra lại kết quả. |

## 6. Cài đặt và sử dụng

### Windows PowerShell — đường chạy khuyến nghị

Tại thư mục gốc repository:

```powershell
./setup-demo.ps1
./run-demo.ps1 --mode pick --web
```

Setup tạo runtime riêng trong `.runtime/` với Python 3.11 và PyBullet dựng sẵn, cài dependency và tải hai model vào `models/hand_landmarker.task`, `models/pose_landmarker_lite.task`. Lần cài đầu cần mạng. Các phiên bản chính: NumPy 1.26.4, MediaPipe 0.10.14, OpenCV contrib 4.10.0.84; xem [requirements-demo.txt](requirements-demo.txt) và [requirements-vision-lock.txt](requirements-vision-lock.txt).

Lệnh chạy mở webcam và GUI PyBullet. Mở `http://127.0.0.1:8765` để xem cảnh Three.js; phần web cần mạng để lấy thư viện/font từ CDN. Dùng `--headless --web` để xem cảnh web thay GUI PyBullet. Ảnh webcam được xử lý cục bộ, không truyền qua HTTP bridge hoặc lưu trong log của ứng dụng.

```powershell
# Đổi camera hoặc tay điều khiển
./run-demo.ps1 --mode pick --web --source 1 --hand Left

# Landmark tổng hợp, vật lý PyBullet thật; không phải đánh giá webcam
./run-demo.ps1 --mode pick --demo --headless --web

# Phần mở rộng: robot đi theo cánh tay trong XYZ
./run-demo.ps1 --mode arm --web
```

Trong `arm`, giữ cánh tay yên rồi nhấn **C**, chờ hiệu chuẩn khoảng 0,6 giây và trạng thái `FOLLOWING`. Chế độ này dùng `arm_vision.py`/MediaPipe Holistic và `arm_control.py`, không tự thực hiện chu trình gắp–thả. IK dùng đích khuỷu và cổ tay, không bảo đảm sao chép mọi góc khớp người. Mất landmark bàn tay riêng lẻ không dừng chế độ này nếu vai–khuỷu–cổ tay vẫn hợp lệ.

Linux có thể cài Python 3.11 trong venv, chạy `python -m pip install -r requirements-demo.txt`, `python -m dev.download_model`, rồi `python main.py --mode pick --web`. Đường chạy Linux chưa được xác nhận lại trong lần lập báo cáo. Xem [README_DEMO.md](README_DEMO.md) để biết hướng dẫn vận hành, runner độc lập và xử lý sự cố.

### Thao tác chế độ gắp hàng

1. Để webcam thấy đủ vai, khuỷu, cổ tay và bàn tay đã chọn. Mở cái–trỏ ổn định; nếu đang PAUSED, đợi thông báo sẵn sàng rồi nhấn **C**.
2. Di chuyển tâm lòng bàn tay trong khung điều khiển. Trên ảnh gương, sang phải tăng X, lên trên tăng Y.
3. Đưa đầu gắp tới hộp được tô sáng và chụm cái–trỏ. Robot tự hạ, gắn và nâng hộp.
4. Di chuyển tới giỏ rồi mở cái–trỏ để robot tự hạ và thả. Nếu mở ngoài giỏ, đưa hộp vào giỏ và chụm/mở lại.
5. Khi mất tracking, mở tay ổn định ít nhất **0,75 giây**, đợi dòng `Tracking stable: tap C once to resume`, rồi nhấn **C** một lần. C nhấn sớm không được lưu chờ. Robot nâng tại vị trí hiện tại trước khi tiếp tục di chuyển ngang.

| Phím | Chức năng |
|---|---|
| **P** | Tạm dừng, giữ vị trí và hộp đang gắp |
| **C** | Xác nhận phục hồi sau tracking ổn định; trong `arm` là hiệu chuẩn lại |
| **R** | Reset cảnh, liên kết và trạng thái điều khiển; lượt đo đang chạy được ghi thất bại |
| **T** | Bắt đầu một lượt đo gắp ở chế độ `pick` |
| **Q / Esc** | Thoát |

Các nút tương ứng có trong cảnh web. Tham số ở `config.py`: workspace pick X = 0,35–0,65 m, Y = −0,25–0,25 m; vận tốc mục tiêu tối đa 0,35 m/s; tỷ lệ chụm/mở 0,30/0,50; xác nhận cử chỉ 0,12 giây; tuổi mẫu tối đa 0,25 giây. Vòng điều phối đặt mục tiêu 60 Hz, **không phải FPS webcam đã đo**.

## 7. Phương pháp đánh giá định lượng

Theo kế hoạch, đo **10 lượt với ít nhất 2 người**, chỉ định ID hộp trước mỗi lượt và reset cảnh giữa các lượt. Giữ nguyên phiên bản; ghi cả lượt lỗi, timeout và reset.

**Thành công:** gắp đúng hộp yêu cầu, thả vào giỏ trong tối đa 30 giây từ lúc bắt đầu và không có lý do thất bại. Báo cáo số lượt thành công/tổng lượt, số lượt gắp nhầm và trung vị thời gian của các lượt thành công, kèm số mẫu dùng tính trung vị. Mục tiêu **8/10** trong kế hoạch là mục tiêu nội bộ, chưa phải kết quả đạt được.

```powershell
./run-demo.ps1 --mode pick --web --operator LuuQuangKhai --trial-box green
```

Nhấn **T** khi sẵn sàng. Đổi `--operator` và `--trial-box` theo người/hộp trong phiên tương ứng. Ứng dụng ghi vào `results/live/<session>/`:

- `trials.csv`: `trial_id,operator,requested_box_id,picked_box_id,placed_in_bin,duration_s,failure_reason`.
- `events.jsonl`: sự kiện điều khiển và vòng đời phiên/lượt thử.
- `session.json`: cấu hình, dependency, Git revision, trạng thái thay đổi mã nguồn và loại đầu vào.

Tổng hợp CSV bằng lệnh sau; thay `SESSION` và `BUILD_ID` bằng giá trị của phiên đo:

```powershell
.runtime/python/python.exe -m dev.run_metrics --input results/live/SESSION/trials.csv --data-kind real --revision BUILD_ID
```

`--demo` ghi riêng vào `results/synthetic/`. Bộ mẫu `dev/sample_data/` dùng kiểm chứng công cụ; không dùng số liệu mẫu để báo cáo hiệu quả webcam. Thời gian hoàn tất lượt gắp khác với thời gian xử lý frame; overlay frame age/processing cũng không phải phép đo camera-to-display đầy đủ.

## 8. Kết quả kiểm chứng và ca lỗi

### Kết quả hiện có

Ngày **17/10/2026**, chạy lại bộ kiểm thử với runtime Windows của dự án:

```powershell
.runtime/python/python.exe -m unittest discover -s tests -v
```

**Kết quả: 54/54 kiểm thử đạt, không có kiểm thử bị bỏ qua; thời gian chạy 22,368 giây trên máy kiểm tra.** Đây là số đo của bộ kiểm thử, không phải thời gian thao tác gắp hàng của người dùng.

Bộ kiểm thử bao gồm mapping/cử chỉ, pause/resume/reset, dữ liệu cũ/sai, ghép pose–hand, ghi kết quả lượt thử, HTTP snapshot, gắp/thả ba hộp với PyBullet thật, khoảng cách attach, workspace IK và điều khiển cánh tay. Kiểm thử model có chạy suy luận MediaPipe; dữ liệu kiểm thử không thay thế thao tác webcam của người dùng.

Tại thời điểm rà soát, các `trials.csv` hiện có trong `results/live/` chỉ chứa hàng tiêu đề. Vì vậy **chưa có tỷ lệ thành công, số lượt gắp nhầm hoặc trung vị thời gian từ người dùng để công bố**. Chưa có video dự phòng và bản ghi ca lỗi webcam trong bộ bằng chứng. Runtime, model và log cục bộ có thể bị Git bỏ qua; cần chủ động lưu bằng chứng phù hợp khi bàn giao.

### Ca lỗi tái lập: mất tracking khi đang mang hộp

| Nội dung | Phân tích |
|---|---|
| Tình huống | Đã gắp hộp, sau đó che vai/khuỷu hoặc bàn tay; một tình huống khác là frame gián đoạn quá ngưỡng. |
| Nguyên nhân | Mẫu thiếu landmark đúng bên tay, ghép cổ tay không hợp lệ hoặc dữ liệu đã cũ; vị trí/cử chỉ không đủ điều kiện phát lệnh. |
| Hành vi thiết kế | Chuyển sang `PAUSED`, giữ vị trí khớp thực và liên kết hộp; không tiếp tục đích cũ, không tự thả. |
| Bằng chứng tự động | `tests/test_control.py` kiểm tra mất một phần cánh tay, ghép sai cổ tay, khoảng trống frame và C nhấn sớm; `tests/test_integration.py` kiểm tra giữ hộp/reset với PyBullet thật. Các kiểm thử này đã đạt trong lần chạy trên. |
| Phục hồi | Hiển thị đủ tay, mở ngón ổn định ít nhất 0,75 giây, chờ thông báo rồi nhấn C; hoặc R để reset. |
| Giới hạn | Đây là tình huống được kiểm chứng bằng dữ liệu kiểm thử. Cần ghi ca webcam thực và gắn log/mốc thời gian. Tracking còn hợp lệ vẫn có thể nhận nhầm cử chỉ khi tay xoay hoặc bị che một phần; PAUSED không giải quyết mọi lỗi nhận diện. |

## 9. Giá trị ứng dụng và hướng phát triển

Demo cho phép thử cách điều khiển trạm chuyển kiện bằng một tay, quan sát hộp đang chọn và phản hồi robot trước khi kết nối thiết bị thật. Sau khi phát triển và kiểm định thêm, hệ thống có thể hỗ trợ đào tạo vận hành hoặc thao tác từ xa trong bối cảnh VinFast/Vin Robotics.

**Ước lượng minh họa, không phải số đo của dự án:** giả sử một trạm xử lý 400 kiện/ca, 60% kiện thuộc phạm vi robot có thể thao tác, và 80% số đó chuyển được sang robot, thì số lượt nâng thủ công có thể chuyển giao là `400 × 0,60 × 0,80 = 192 lượt/ca`. Các giả định phải được đo lại tại trạm thật; con số này không chứng minh giảm chấn thương, tiết kiệm thời gian hay đáp ứng tải trọng.

Hướng phát triển: hoàn tất đánh giá nhiều người và nhiều điều kiện ánh sáng; hiệu chỉnh camera/workspace; bổ sung phản hồi khi tracking yếu và replay; thử dây chuyền động; sau đó nghiên cứu robot thật với kiểm tra va chạm, lực kẹp, dừng khẩn cấp và độ trễ truyền lệnh. Mô phỏng hiện tại chưa tránh vật cản tự động; robot và hộp không mô phỏng tiếp xúc ngón kẹp chính xác.

## 10. Kịch bản trình bày và bàn giao

| Thời gian | Người phụ trách | Nội dung |
|---|---|---|
| 0:00–1:00 | Lưu Quang Khải | Bài toán, người dùng VinFast/Vin Robotics và phạm vi mô phỏng |
| 1:00–3:00 | Đào Thị Huyền, Nguyễn Đức Đông | Webcam, landmark từ vai đến ngón tay, chọn bên tay và thao tác cử chỉ |
| 3:00–5:00 | Vũ Hải Minh | Robot gắp–chuyển–thả; cho giám khảo chỉ định hộp hoặc thử điều khiển |
| 5:00–7:00 | Đặng Đỉnh Đoàn, Lưu Quang Khải hỗ trợ | Số đo, ca lỗi, trụ cột áp dụng, tác động ước lượng và giới hạn |
| 7:00–10:00 | Cả 5 thành viên | Hỏi đáp về từng module và toàn bộ hệ thống |

Trước buổi demo cần hoàn tất:

- [ ] Thử webcam và thao tác trực tiếp trên đúng máy/phòng demo; kiểm tra riêng che vai/khuỷu và che bàn tay.
- [ ] Đo đủ 10 lượt với ít nhất 2 người; xuất báo cáo gắn phiên bản, giữ toàn bộ lượt thất bại.
- [ ] Ghi ca lỗi thực tế, nguyên nhân, cách phục hồi và mốc log/video.
- [ ] Quay video dự phòng thấy cả webcam và simulator; thử phát offline.
- [ ] Cập nhật kết quả thật trong báo cáo và [DEMO_SCRIPT.md](DEMO_SCRIPT.md); tập trình bày trong 10 phút.
- [ ] Xác nhận repository Public và thành viên cùng tham gia phát triển; **từng thành viên tự nộp URL repo chung lên VLearn cá nhân**, ghi tên nhóm, trưởng nhóm và vai trò của mình.

## 11. Cấu trúc mã nguồn và tài liệu

| Đường dẫn | Nội dung |
|---|---|
| `main.py`, `contracts.py`, `config.py` | Điểm chạy tích hợp, kiểu dữ liệu và cấu hình chung |
| `vision.py`, `control.py` | Nhận diện và điều khiển chu trình gắp hàng |
| `arm_vision.py`, `arm_control.py` | Phần mở rộng theo chuyển động cánh tay |
| `simulation/` | PyBullet, cảnh web và HTTP bridge |
| `metrics.py`, `dev/run_metrics.py` | Ghi log, lượt đo và tổng hợp báo cáo |
| `dev/`, `tests/` | Runner từng module, đầu vào tổng hợp và kiểm thử |
| `models/`, `requirements*.txt` | Hướng dẫn model và dependency |
| `setup-demo.ps1`, `run-demo.ps1` | Thiết lập và chạy runtime Windows |
| `run_holistic.py`, `run_pipeline.py`, `train_hand.py`, `sim_env.py` | Pipeline thử nghiệm ban đầu; huấn luyện CMU là tùy chọn ngoài MVP |
| [README_DEMO.md](README_DEMO.md) | Hướng dẫn vận hành và kiểm chứng chi tiết |
| [HACKATHON_PLAN.md](HACKATHON_PLAN.md), [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | Kế hoạch phân công và kịch bản demo |
| [results/README.md](results/README.md) | Quy ước lưu bằng chứng và kết quả |
| [docs/GUIDE.txt](docs/GUIDE.txt), `index.html` | Yêu cầu hackathon và trang đề bài gốc |
