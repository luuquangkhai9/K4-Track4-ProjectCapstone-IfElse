# Pose Lite + Hand Landmarker pretrained

Chạy `python -m dev.download_model` để tải đủ hai model chính thức:

- `hand_landmarker.task`: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
- `pose_landmarker_lite.task`: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task

Model được Git ignore; chương trình không tự tải khi chạy demo. Script tải bỏ qua
file đã tồn tại. `config.py` quy định đường dẫn của cả hai model.

Tài liệu: [Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python),
[Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python).
