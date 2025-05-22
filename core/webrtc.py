from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from enums.camera_enum import CameraDirection
from core.video import CustomVideoStreamTrack
from collections import defaultdict
from util.my_logger import logger
import json
import os

# 피어 연결을 저장할 딕셔너리
pcs = defaultdict(dict)

direction_to_video = {direction: CustomVideoStreamTrack(direction) 
                      for direction in CameraDirection.__members__.keys()}

# 카메라 ID에 대한 RTCPeerConnection 생성 및 이벤트 핸들러 등록
def create_peer_connection(direction):
    # 피어 연결 생성
    config = RTCConfiguration(
        iceServers=[
            RTCIceServer(
                urls=os.getenv("TURN_URL"),  # 단일 URL 문자열로 제공
                username=os.getenv("TURN_USERNAME"),
                credential=os.getenv("TURN_PASSWORD")
            )
        ]
    )
    pc = RTCPeerConnection()
    # 비디오 트랙 추가
    video = direction_to_video.get(direction)
    pc.addTrack(video)

    camera_id = CameraDirection[direction].value

    # 연결 상태 변경 이벤트 핸들러
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"카메라 {camera_id} 연결 상태: {pc.connectionState}")
        if pc.connectionState == "failed":
            logger.warning(f"카메라 {camera_id} 연결 실패")
            await pc.close()

    # ICE 연결 상태 변경 이벤트 핸들러
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        logger.info(f"카메라 {camera_id} ICE 연결 상태: {pc.iceConnectionState}")

    # ICE 수집 상태 변경 이벤트 핸들러
    @pc.on("icegatheringstatechange")
    async def on_icegatheringstatechange():
        logger.info(f"카메라 {camera_id} ICE 수집 상태: {pc.iceGatheringState}")
    logger.info(f"카메라 {camera_id}에 대한 PeerConnection 생성 완료")
    return pc

# 특정 peer connection을 정리하는 함수
async def close_peer_connection(client_id, camera_id):
    if client_id in pcs and camera_id in pcs[client_id]:
        logger.info(f"클라이언트 {client_id}, 카메라 {camera_id}에 대한 기존 연결 종료")
        await pcs[client_id][camera_id].close()
        del pcs[client_id][camera_id]

# Offer를 처리하고 Answer를 생성하는 함수
async def process_offer(direction, camera_id, client_id, offer_data):
    try:
        logger.info(f"카메라 {camera_id}에 대한 Offer 처리 시작")

        # 이미 존재하는 PeerConnection이 있으면 닫기
        await close_peer_connection(client_id, camera_id)

        # 새 PeerConnection 생성 및 이벤트 핸들러 등록
        pc = create_peer_connection(direction)
        pcs[client_id][camera_id] = pc

        # Offer 데이터 구조 확인 및 처리
        if isinstance(offer_data, dict) and "body" in offer_data:
            offer_body = offer_data["body"]
        else:
            offer_body = offer_data

        # Offer 내용 로깅
        logger.info(f"카메라 {camera_id} Offer 데이터: type={offer_body.get('type')}, SDP 길이={len(offer_body.get('sdp', ''))}")

        # SDP 및 타입 확인
        if not offer_body.get("sdp") or not offer_body.get("type"):
            logger.error(f"카메라 {camera_id}: 유효한 SDP 또는 타입이 없습니다")
            return None

        # Offer 생성 및 설정
        offer = RTCSessionDescription(
            sdp=offer_body.get("sdp"),
            type=offer_body.get("type")
        )

        # 원격 설명(Offer) 설정
        await pc.setRemoteDescription(offer)
        logger.info(f"카메라 {camera_id}: 원격 설명(Offer) 설정 완료")

        # Answer 생성
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        logger.info(f"카메라 {camera_id}: 로컬 설명(Answer) 설정 완료")

        # Answer 데이터 생성
        answer_data = {
            "key": camera_id,
            "body": {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
            }
        }

        # Answer JSON 생성 및 전송
        answer = json.dumps(answer_data)

        return answer

    except Exception as e:
        logger.error(f"카메라 {camera_id} 처리 중 예외 발생: {str(e)}")
        await close_peer_connection(client_id, camera_id)
        
        return None
    
# 모든 peer connection을 정리하는 함수
async def cleanup():
    logger.info("모든 연결 정리 시작")
    for pc in [pc for cam_dict in pcs.values() for pc in cam_dict.values()]:
        try:
            await pc.close()
        except Exception as e:
            logger.error(f"카메라 연결 정리 중 오류: {str(e)}")

    pcs.clear()
    logger.info("모든 연결 정리 완료")