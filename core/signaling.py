from enums.camera_enum import CameraDirection
from core.webrtc import process_offer
from util.my_logger import logger
import websockets
import stomper
import json
import os

WS_URL = os.getenv("WS_URL")

# STOMP subscribe 함수
async def subscribe(endpoint, websocket):
    message = stomper.subscribe(endpoint, idx="all")
    await websocket.send(message)
    logger.info(f"{endpoint}에 대한 구독 완료")

# STOMP publish 함수
async def publish(endpoint, payload, websocket):
    message = stomper.send(endpoint, payload)
    await websocket.send(message)
    logger.info(f"{endpoint}에 대한 메시지 전송 완료")

# STOMP connect 함수
async def connect(websocket):
    await websocket.send("CONNECT\naccept-version:1.0,1.1,2.0\n\n\x00\n")
    logger.info("STOMP 프로토콜 연결 메시지 전송")

# 클라이언트 id, 카메라 방향, 카메라 id를 추출하는 함수
async def parse_offer(body):
    direction = None
    client_id = None
    camera_id = None
    if isinstance(body, dict):
        if "direction" in body and "client_id" in body:
            direction = body.get("direction")
            client_id = body.get("client_id")
    
    if direction is not None and direction in CameraDirection.__members__.keys():
        camera_id = CameraDirection[direction].value
        logger.info(f"카메라 ID {camera_id}에 대한 Offer 처리")

    return direction, client_id, camera_id

# STOMP 메시지를 파싱해 endpoint와 body를 리턴하는 함수
def parse_message(message):
    data = stomper.unpack_frame(message)

    if data.get("cmd") != "MESSAGE": return None, None

    # 목적지 및 본문 추출
    endpoint = data.get("headers", {}).get("destination", "")
    body_str = data.get("body", "")

    # 메시지 로깅 (긴 메시지는 일부만)
    preview_length = min(100, len(body_str))
    logger.info(f"메시지 수신: 목적지={endpoint}, 본문 미리보기={body_str[:preview_length]}...")

    # JSON 파싱
    try:
        body = json.loads(body_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {str(e)}")
        return None, None
    
    return endpoint, body

# 메시지 처리 함수
async def process_message(message, websocket):
    try:
        endpoint, body = parse_message(message)
        if (endpoint is None and body is None): return

        if endpoint == "/topic/offer":
            direction, client_id, camera_id = await parse_offer(body)

            if camera_id is None: 
                logger.warning("카메라 ID를 찾을 수 없어 Offer를 처리할 수 없습니다")
                return

            answer = await process_offer(direction, camera_id, client_id, body)
            if answer is None: return

            await publish(f"/app/answer/{client_id}/{direction}", answer, websocket)

    except Exception as e:
        logger.error(f"메시지 처리 중 오류 발생: {str(e)}")

# Signaling 메시지를 listening 하는 함수
async def execute():
    try:
        async with websockets.connect(WS_URL) as websocket:
            logger.info("Signaling 서버에 WebSocket 연결 성공")            

            await connect(websocket)
            await subscribe("/topic/offer", websocket)

            # 메시지 처리 루프
            while True:
                message = await websocket.recv()
                await process_message(message, websocket)

    except Exception as e:
        logger.error(f"WebSocket 연결 중 오류 발생: {str(e)}")