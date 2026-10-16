# Kết quả đo thật

Chưa có lượt thử thật, ca lỗi quan sát hoặc video. Không dùng dữ liệu mẫu để điền báo cáo này.

- Dữ liệu tổng hợp để phát triển nằm tại `dev/sample_data/`; output mặc định của runner nằm trong thư mục tạm, ngoài `results/`.
- Mỗi lần đo thật tạo một thư mục mới: `results/<build>-<session>/`.
- Thư mục phiên đo chứa `run.json` (phiên bản, nguồn dữ liệu, thời điểm tạo), `trials.csv`, `events.csv`, `summary.json`, `summary.md`.
- Giữ cả lượt lỗi/hủy/reset, mỗi lượt một ID duy nhất; không ghi đè để thay bằng lượt đẹp hơn.
- Giữ nguyên phiên bản trong cả bộ 10 lượt, ít nhất hai người thao tác; reset cảnh giữa các lượt.
- `duration_s` tính từ tín hiệu bắt đầu đến xác nhận hộp ổn định trong giỏ hoặc kết thúc thất bại. Hết 30 giây thì kết thúc lượt với `failure_reason=timeout`.
- Khi reset/hủy giữa lượt: ghi sự kiện, lưu lượt thất bại với thời gian thực đã trôi qua, sau đó mới reset cảnh; lượt tiếp theo dùng ID mới.
- ID hộp dùng đúng ID ổn định do TV3 bàn giao; các tên `box_red/blue/green` chỉ là ID của mẫu.
- Video và ghi chú ca lỗi thực tế bổ sung sau khi TV1–TV3 có bản tích hợp chạy được.

Tạo báo cáo từ CSV thật (thay tên file/phiên bản bằng giá trị thật):

```bash
python -m dev.run_metrics --input /path/to/measured-trials.csv --events /path/to/measured-events.csv --data-kind real --revision <measured-build> --output results/<unique-session>
```

File mẫu không được đổi nhãn thành dữ liệu thật. CLI yêu cầu chọn nguồn dữ liệu rõ ràng và chặn mẫu đóng gói sẵn khi chọn `real`.
