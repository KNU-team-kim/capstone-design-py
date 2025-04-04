import asyncio
import json
import websockets
import stomper
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from av import VideoFrame
import cv2
from ultralytics import YOLO
import fractions
import env

yolo_model = YOLO("yolov8n.pt")
pcs = []

# openCV로 받아온 프레임을 yolo로 처리해 webrtc track 형식으로 반환하는 클래스
class CustomVideoStreamTrack(VideoStreamTrack):
    def __init__(self, camera_id):
        super().__init__()
        self.cap = cv2.VideoCapture(camera_id)
        self.frame_count = 0

    async def recv(self):
        self.frame_count += 1
        print(f"Sending frame {self.frame_count}")
        ret, frame = self.cap.read()
        if not ret:
            print("Failed to read frame from camera")
            return None
        
        results = yolo_model(frame)

        annotated_frame = results[0].plot()

        annotated_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(annotated_frame, format="rgb24")
        video_frame.pts = self.frame_count
        video_frame.time_base = fractions.Fraction(1, 30)
        return video_frame
    

# signaling server에 접속하는 함수
async def connect():
    global pcs

    ws_url = f"ws://{env.SERVER_URL}:8080/signaling"
    print(f"Connecting to signaling server at: {ws_url}")

    async with websockets.connect(ws_url) as websocket:
        # 초기 연결
        await websocket.send("CONNECT\naccept-version:1.0,1.1,2.0\n\n\x00\n")
        
        # offer 이벤트 구독
        sub_offer = stomper.subscribe("/topic/offer/1", idx="1")
        await websocket.send(sub_offer)

        print("Connected to signaling server and subscribed to topics")

        # 연결 관리를 위한 맵
        pc_map = {}

        while True:
            message = await websocket.recv()
            data = stomper.unpack_frame(message)

            if (data.get("cmd") != "MESSAGE"): continue

            endpoint = data.get("headers").get("destination")
            body_str = data.get("body")
            body = json.loads(body_str)

            # offer 수신시 실행
            if (endpoint == "/topic/offer/1"):
                print("[OFFER] receive offer: " + body_str)
                
                # offer 파싱 (ICE 후보가 이미 포함됨)
                offer_data = body.get("offer", {})
                sdp = offer_data.get("sdp")
                
                if not sdp:
                    print("Error: SDP missing in offer")
                    continue

                # RTCSessionDescription 생성
                offer = RTCSessionDescription(sdp=sdp, type="offer")

                # peer connection 생성 (STUN 서버 설정 추가)
                # configuration = {
                #     "urls": [
                #         {"iceServers": ["stun:stun.l.google.com:19302"]}
                #     ]
                # }
                # ice_server = RTCIceServer(urls='stun:stun.l.google.com:19302')
                ice_server = RTCIceServer(
                    urls="turn:15.164.163.252:3478",
                    username="turn", 
                    credential="capstonedesign"
                )
                pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[ice_server]))
                # pc = RTCPeerConnection(iceServers=[{"urls": ["stun:stun.l.google.com:19302"]}])
                # pc = RTCPeerConnection(configuration=configuration)
                pc_id = body.get("id", "1")
                pc_map[pc_id] = pc
                pcs.append(pc)

                # 연결 상태 모니터링
                @pc.on("connectionstatechange")
                async def on_connectionstatechange():
                    print(f"Connection state is {pc.connectionState}")
                    if pc.connectionState == "failed" or pc.connectionState == "closed":
                        if pc in pcs:
                            pcs.remove(pc)
                        for key, value in list(pc_map.items()):
                            if value == pc:
                                del pc_map[key]
                                break

                # 비디오 트랙 추가
                video = CustomVideoStreamTrack(1) # 맥에서 테스트라 1
                pc.addTrack(video)

                # 원격 설명 설정 (이미 모든 ICE 후보가 포함됨)
                await pc.setRemoteDescription(offer)

                # answer 생성 및 모든 ICE 후보 수집
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                
                # ICE 수집이 완료될 때까지 잠시 대기
                print("Waiting for ICE gathering to complete...")
                await asyncio.sleep(1)  # ICE 수집 시간 제공
                
                # 최종 LocalDescription 가져오기 (모든 ICE 후보 포함)
                complete_answer = pc.localDescription
                
                # 최종 Answer 전송
                answer_message = {
                    "type": "answer",
                    "answer": {
                        "sdp": complete_answer.sdp,
                        "type": complete_answer.type
                    },
                    "id": pc_id
                }
                
                send_answer = stomper.send("/app/answer/1", json.dumps(answer_message))
                await websocket.send(send_answer)
                print(f"Complete answer sent for connection {pc_id}")

            # ICE candidate 처리 - Vanilla ICE에서는 불필요하지만 하위 호환성을 위해 유지
            elif (endpoint == "/topic/iceCandidate/1"):
                print("[ICE] Ignoring individual ICE candidate as we're using Vanilla ICE method")

# 메인 실행
if __name__ == "__main__":
    print("Starting WebRTC server")
    try:
        asyncio.get_event_loop().run_until_complete(connect())
    except Exception as e:
        print(f"Error: {e}")
    finally:
        for pc in pcs:
            try:
                asyncio.get_event_loop().run_until_complete(pc.close())
            except:
                pass
        print("All connections closed")