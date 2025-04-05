import cv2
import subprocess
from ultralytics import YOLO
import logging
import env

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
    f'rtsp://{env.SERVER_URL}:8554/test'
]

logging.getLogger("ultralytics").setLevel(logging.ERROR)

yolo_model = YOLO("yolov8n.pt")

# FFmpeg 프로세스 실행
pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)

# 카메라 영상 처리
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()

    if not ret:
        break

    results = yolo_model(frame)
    annotated_frame = results[0].plot()
    
    pipe.stdin.write(annotated_frame.tobytes())