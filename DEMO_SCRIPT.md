# Kịch bản demo 10 phút — TV4 chuẩn bị

**Trạng thái:** chưa có kết quả chạy thật hoặc video. Các số liệu trong bộ dữ liệu mẫu không được dùng để thuyết trình thành tích.

| Thời gian | Người phụ trách | Nội dung |
|---|---|---|
| 0:00–1:00 | TV1 | Người vận hành trạm chuyển kiện, mục tiêu điều khiển robot bằng một tay; nêu phạm vi mô phỏng |
| 1:00–3:00 | TV2 | Webcam/landmark, ảnh gương, di chuyển tay và con trỏ; giải thích chụm/mở |
| 3:00–5:00 | TV3 | Hộp được chỉ định, gắp–nâng–chuyển–thả; mời giám khảo chọn hộp; chuẩn bị reset |
| 5:00–7:00 | TV4, TV1 hỗ trợ | Bằng chứng, ca lỗi và giới hạn; xem lời dẫn bên dưới |
| 7:00–10:00 | Cả nhóm | Hỏi đáp theo phần sở hữu; hiểu toàn bộ luồng |

## Phần TV4: phút 5:00–7:00

### 5:00–5:40 — Bảng đo

> “Nhóm đo trên phiên bản **[CHỜ BUILD THẬT]**, có **[CHỜ SỐ NGƯỜI THẬT]** người trực tiếp thao tác. Mỗi lượt được chỉ định hộp trước và tính giờ từ tín hiệu bắt đầu. Thành công là lấy đúng hộp, thả vào giỏ trong 30 giây. Nhóm giữ cả lượt thất bại và reset.”
>
> “Kết quả: **[CHỜ KẾT QUẢ]/10** lượt thành công, **[CHỜ KẾT QUẢ]** lượt gắp nhầm. Trung vị thời gian của **[CHỜ n]** lượt thành công là **[CHỜ KẾT QUẢ]** giây.”

Hiển thị `results/<session>/summary.md` và có thể mở `trials.csv` để kiểm tra. Nếu chưa đủ 10 lượt/hai người, nói rõ số đã đo; không đọc thành `/10` hoàn chỉnh. Nếu không có lượt thành công, nói chưa tính được trung vị.

### 5:40–6:20 — Một ca lỗi

> “Ở tình huống **[CHỜ QUAN SÁT THẬT: che/nghiêng tay]**, hệ thống **[CHỜ HÀNH VI THỰC]**. Log/video ở **[CHỜ MỐC THỜI GIAN]** cho thấy **[CHỜ BẰNG CHỨNG]**. Nhóm phục hồi bằng **[CHỜ THAO TÁC ĐÃ KIỂM TRA]**.”

Cho xem trực tiếp hoặc đoạn video thật: mất tracking, PAUSED, hộp có được giữ không, phục hồi. Nếu cử chỉ sai trong khi tracking vẫn hợp lệ, nêu đúng hiện tượng đó; không khẳng định pause xử lý mọi lỗi. Giữ nút reset sẵn theo phím TV1 xác nhận.

### 6:20–7:00 — Kiến thức và giới hạn

> “Hình học nằm ở ánh xạ tay sang mặt bàn và IK; biểu diễn nằm ở landmark và máy trạng thái. Thời gian và bất định thể hiện ở xử lý mẫu cũ/mất tracking. Phần bằng chứng là CSV đủ lượt, ca lỗi và phiên bản xác định.”
>
> “Đây là demo mô phỏng. Gắp được đơn giản hóa bằng liên kết cố định; mở tay ngoài giỏ được chặn để hỗ trợ thao tác. Nhóm chưa chứng minh lực kẹp, tải trọng công nghiệp hoặc cải thiện năng suất thực tế.”

TV1/TV3 xác nhận mô tả khớp bản cuối trước khi đọc. Nếu ước lượng tác động, dùng công thức và ghi công khai giả định; không dùng kết quả mẫu hoặc mô phỏng để khẳng định đã giảm chấn thương.

## Nếu demo trực tiếp hỏng

Nói rõ: “Đây là video dự phòng quay trên phiên bản **[BUILD]**, không phải luồng trực tiếp.” Mở `results/<session>/backup-demo.mp4` đã phát thử offline. Nếu video cũng chưa có, nói phần chưa chứng minh; không thay bằng fake.

## Câu hỏi TV4 cần trả lời

- **8/10 đã đạt chưa?** Đọc kết quả thật; 8/10 ban đầu là mục tiêu. Bộ mẫu có đáp án 8/10 chỉ để kiểm tra công cụ.
- **Có bỏ lượt xấu không?** Giữ mọi lượt trong bộ đã chốt, cả timeout/reset; ID duy nhất, không ghi đè.
- **Median tính trên gì?** Chỉ các lượt thành công và luôn báo n; không gọi đó là độ trễ camera.
- **Ai xác nhận đặt thành công?** TV3 xác nhận hộp đã thả và nằm ổn định trong giỏ; logger không suy ra từ lệnh RELEASE.
- **Đổi code giữa chừng thì sao?** Ghi phiên bản mới, đo lại phần chịu ảnh hưởng; không gộp thành một bộ đo cùng phiên bản.
- **Mất tracking có luôn an toàn không?** Chỉ kết luận theo ca thực đã thử, phân biệt mất tracking với nhận nhầm cử chỉ khi tracking còn tồn tại.

## Chốt trước khi lên trình bày

- [ ] TV1 xác nhận build, lệnh chạy và phím pause/resume/reset/quit.
- [ ] TV2/TV4 trực tiếp thao tác đủ lượt; CSV thật không chứa dữ liệu mẫu.
- [ ] Điền số liệu thật, n và đường dẫn báo cáo ở lời dẫn.
- [ ] Ghi ca lỗi thực tế, nguyên nhân có bằng chứng và cách phục hồi đã thử.
- [ ] Video thấy webcam và simulator, phát được offline; thay placeholder đường dẫn.
- [ ] Cả nhóm tập một lượt, TV4 nói trong hai phút.
