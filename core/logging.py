from util.my_logger import logger
import requests
import uuid
import cv2
import io
import os

API_URL = os.getenv("API_URL")

def send_request(direction, current_counter, confidences, annotated_frame):
    logger.info(f"{direction} 변경 감지: {current_counter}")

    # 파일 이름 UUID로 생성
    generated_id = str(uuid.uuid4())
    file_name = f"{generated_id}.jpg"

    # Presigned URL 요청
    try:
        res = requests.get(f"{API_URL}/api/s3/presigned/upload?fileName={file_name}")
        res.raise_for_status()
        presigned_url = res.text

        if presigned_url:
            # 이미지 메모리 버퍼로 JPEG 인코딩
            _, img_encoded = cv2.imencode(".jpg", annotated_frame)
            img_bytes = io.BytesIO(img_encoded.tobytes())

            # Presigned URL로 업로드
            upload_res = requests.put(presigned_url, data=img_bytes.getvalue())
            upload_res.raise_for_status()
            logger.info(f"이미지 S3 업로드 성공 {presigned_url}")

    except requests.exceptions.RequestException as e:
        logger.error(f"presigned URL 요청/업로드 실패: {e}")

    # 5. 로그 서버에 데이터 저장 요청
    payload = {
        "classTypes": [cls.name for cls in current_counter.keys()],
        "confidence": round(sum(confidences) / len(confidences), 2),
        "fileName": file_name,
        "directionType": direction
    }

    try:
        log_res = requests.post(
            f"{API_URL}/api/logs",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        log_res.raise_for_status()
        logger.info(f"로그 저장 성공: {log_res.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"로그 저장 실패: {e}")