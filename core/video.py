from enums.color_mapper import color_names, colors
from enums.camera_enum import CameraDirection
from enums.class_enum import name_to_enum
from datetime import datetime, timezone
from core.logging import send_request
from aiortc import VideoStreamTrack
from util.my_logger import logger
from collections import Counter
from core.yolo import load_yolo
import concurrent.futures
from av import VideoFrame
import numpy as np
import fractions
import logging
import time
import cv2

logging.getLogger("ultralytics").setLevel(logging.CRITICAL)

trt_model = load_yolo()

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# openCV로 받아온 프레임을 webrtc track 형식으로 반환하는 클래스
class CustomVideoStreamTrack(VideoStreamTrack):
    def __init__(self, direction):
        super().__init__()
        self.direction = direction
        self.camera_id = CameraDirection[direction].value
        self.cap = cv2.VideoCapture(self.camera_id)

        # 객체 인식 로그 용도 카운터
        self.previous_counter = Counter()
        self.last_detected_counter = Counter()
        self.change_stable_count = 0
        self.required_stability_frames = 5

        # 해상도 설정
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 15)

        self.frame_count = 0

        # 비디오 해상도 확인
        ret, frame = self.cap.read()
        if ret:
            self.height, self.width, _ = frame.shape
            logger.info(f"카메라 {self.camera_id} 해상도: {self.width}x{self.height}")
        else:
            self.height, self.width = 480, 640
            logger.warning(f"카메라 {self.camera_id} 해상도를 가져올 수 없습니다. 기본값으로 설정: {self.width}x{self.height}")

        # 색상 표시할 박스 크기
        self.box_size = 10

        # 카메라별 로그 시간 초기화
        self.last_logged_ts = -1

        logger.info(f"카메라 {self.camera_id} 초기화 완료")

    async def recv(self):
        self.frame_count += 1
        ret, frame = self.cap.read()
        if not ret:
            logger.warning(f"카메라 {self.camera_id}에서 프레임을 읽지 못했습니다")
            # 비디오가 실패하면 검은색 프레임 생성
            annotated_frame = self.create_error_frame()
        else:
            # 현재 시간 가져오기
            now_ts = int(time.time())
            now_utc = datetime.utcfromtimestamp(now_ts).replace(tzinfo=timezone.utc)

            # 10초 단위 색상 인덱스 계산
            color_index = (now_ts // 10) % len(colors)
            current_color = colors[color_index]

            # 10초 단위일 경우에만 로그 출력 (중복 방지)
            if now_ts % 10 == 0 and now_ts != self.last_logged_ts:
                color_name = color_names[current_color]
                logger.info(f"카메라 {self.camera_id} - 색상 변경: {color_name}")
                self.last_logged_ts = now_ts
                
            try:
                # YOLO 모델로 객체 감지 수행
                results = trt_model(frame)

                current_counter, confidences = self.update_status(results)
                annotated_frame = results[0].plot()
                if self.check_condition(current_counter, confidences):
                    executor.submit(send_request, self.direction, current_counter, confidences, annotated_frame)

                # 박스 영역 계산
                x1, y1 = 0, 0
                x2 = min(self.box_size, self.width)
                y2 = min(self.box_size, self.height)

                # 박스 색상 적용
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), current_color, -1)

                # BGR에서 RGB로 색상 변환 (WebRTC는 RGB 형식 사용)
                annotated_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            except Exception as e:
                # YOLO 처리 중 오류 발생 시
                logger.error(f"카메라 {self.camera_id} - YOLO 처리 중 오류: {e}")
                annotated_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # 원본 프레임 사용

        # VideoFrame 생성 및 반환
        video_frame = VideoFrame.from_ndarray(annotated_frame, format="rgb24")
        video_frame.pts = self.frame_count
        video_frame.time_base = fractions.Fraction(1, 30)
        return video_frame
    
    # 카메라 오류 메시지가 있는 검은색 배경 프레임 생성
    def create_error_frame(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        return frame
    
    # counter 및 confidence 갱신
    def update_status(self, results):
        boxes = results[0].boxes
        current_counter = Counter()
        confidences = []

        if boxes is not None:
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                class_name = trt_model.names[cls_id].lower()

                enum_class = name_to_enum.get(class_name)
                if enum_class:
                    current_counter[enum_class] += 1
                    confidences.append(conf) 
        
        return current_counter, confidences
    
    # 조건에 맞을 경우 로그 저장 요청
    def check_condition(self, current_counter, confidences):
        if current_counter != self.previous_counter:
            if current_counter == self.last_detected_counter:
                self.change_stable_count += 1
            else:
                self.change_stable_count = 1
                self.last_detected_counter = current_counter

            if self.change_stable_count >= self.required_stability_frames:
                self.previous_counter = current_counter
                self.change_stable_count = 0
                if len(confidences) > 0: return True
        else:
            self.change_stable_count = 0
        
        return False