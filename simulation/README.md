# Robot Pick Cell

Môi trường 3D CPU-only cho demo robot gắp hàng từ băng chuyền vào giỏ. Băng chuyền cấp từng sản phẩm; sản phẩm tới vạch cuối sẽ dừng chờ gắp. Nếu chưa được gắp, sản phẩm tiếp theo vẫn ra và xếp phía sau với khoảng cách an toàn. Khi sản phẩm ở đầu hàng được gắp đi, hàng chờ tự tiến lên vạch. Cảnh dùng Three.js theo cách dựng của thư mục `viz/` trong bài lab tham khảo; bridge điều khiển dùng Python standard library, không cần cài package Python.

## Chạy

Từ gốc repo:

```powershell
python simulation/serve.py
```

Mở `http://127.0.0.1:8765`. Cần kết nối mạng để tải Three.js r128 và font giao diện từ CDN. Kéo chuột để xoay cảnh, cuộn để phóng to/thu nhỏ. Nút **Chạy demo gắp hàng** phát một chu trình mẫu; bộ mô phỏng vẫn ở trạng thái chờ lệnh để nhận điều khiển ngoài.

## Gửi lệnh điều khiển

`POST http://127.0.0.1:8765/api/command` với JSON. Gửi lại mỗi frame điều khiển (thường 15–30 Hz); simulation luôn dùng lệnh mới nhất.

```json
{
  "target": { "x": -1.3, "y": 0.85, "z": -1.1 },
  "grip": 1
}
```

`target` là vị trí đầu kẹp sau khi bộ chuyển đổi keypoints ánh xạ sang hệ tọa độ thế giới của simulation, đơn vị mét. Trục `x` chạy dọc băng chuyền, `y` hướng lên từ mặt sàn và `z` là chiều sâu. Lệnh chỉ được nhận trong giới hạn tọa độ `x ∈ [-3.2, 3.2]`, `y ∈ [0.55, 3.0]`, `z ∈ [-2.5, 2.5]` và bán kính với vai robot `(0, 1.22, 0)` không quá `2.62 m`. `grip` bằng `1` để đóng kẹp và `0` để mở. Có thể dùng `gripper` thay cho `grip`.

Nếu bộ chuyển đổi gửi keypoints đã ở hệ tọa độ simulation, có thể đặt điểm cổ tay làm mục tiêu:

```json
{ "keypoints": { "wrist": { "x": -1.3, "y": 0.85, "z": -1.1 } }, "grip": 0 }
```

Ví dụ gửi từ Python:

```python
import json
import urllib.request

command = {"target": {"x": -1.3, "y": 0.85, "z": -1.1}, "grip": 0}
request = urllib.request.Request(
    "http://127.0.0.1:8765/api/command",
    data=json.dumps(command).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
print(urllib.request.urlopen(request).read().decode())
```

`GET /api/health` báo bridge sẵn sàng. `GET /api/command?after=<sequence>` trả lệnh mới nếu có; trình duyệt tự polling endpoint này. HTTP bridge chỉ bind vào `127.0.0.1` để nhận lệnh từ cùng máy.
