from util.my_logger import logger
from ultralytics import YOLO
import os

def load_yolo():
    # TensorRT 엔진 파일이 존재하는지 확인
    engine_path = "best.engine"

    if not os.path.exists(engine_path):
        logger.info("TensorRT 엔진 파일이 없습니다. 변환을 시작합니다...")
        yolo_model = YOLO("best.pt")
        yolo_model.export(format="engine")
        logger.info("모델 변환 완료")

    # 엔진 파일 로드
    trt_model = YOLO(engine_path)
    logger.info("TensorRT 엔진 로드 완료")

    return trt_model