import cv2
import subprocess
from ultralytics import YOLO
import logging
import env
import time

# FFmpeg 명령어 설정
cmd = [
    'ffmpeg',
    '-f', 'rawvideo',
    '-pix_fmt', 'bgr24',
    '-s', '640x480',
    '-r', '10',
    '-i', '-',
    '-c:v', 'libx264',
    '-preset', 'ultrafast',
    '-tune', 'zerolatency',
    '-f', 'rtsp',
    f'rtsp://{env.SERVER_URL}:8554/right'
]

# YOLO 로그 레벨 낮추기
logging.getLogger("ultralytics").setLevel(logging.ERROR)

# YOLO 모델 로드
yolo_model = YOLO("yolov8n.pt")

# FFmpeg 파이프 열기
pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)

# 카메라 열기
cap = cv2.VideoCapture(0)

# 색 순환을 위한 변수들
colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]  # 빨강, 초록, 파랑 (BGR)
color_index = 0
last_color_change = time.time()
color_interval = 0.5  # 색 바꾸는 주기 (초)

# 색 박스를 프레임에 그리는 함수
def overlay_color_box(frame):
    global color_index, last_color_change
    current_time = time.time()

    # 주기적으로 색상 변경
    if current_time - last_color_change > color_interval:
        color_index = (color_index + 1) % len(colors)
        last_color_change = current_time

    # 색 박스 오버레이 (좌상단 100x100)
    cv2.rectangle(frame, (0, 0), (100, 100), colors[color_index], -1)
    return frame

# 메인 루프
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # YOLO 추론
    results = yolo_model(frame)
    annotated_frame = results[0].plot()

    # 색 박스 오버레이 추가
    final_frame = overlay_color_box(annotated_frame)

    # FFmpeg 파이프로 전송
    pipe.stdin.write(final_frame.tobytes())

