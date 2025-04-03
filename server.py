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
pcs = {}
video = None

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

    async with websockets.connect(ws_url) as websocket:
        # 초기 연결
        await websocket.send("CONNECT\naccept-version:1.0,1.1,2.0\n\n\x00\n")
        
        # offer 이벤트 구독
        sub_offer = stomper.subscribe("/topic/offer", 0)
        await websocket.send(sub_offer)

        while True:
            message = await websocket.recv()
            data = stomper.unpack_frame(message)

            if (data.get("cmd") != "MESSAGE"): continue

            endpoint = data.get("headers").get("destination")
            body_str = data.get("body")
            body = json.loads(body_str)

            # offer를 수신했다면
            if (endpoint == "/topic/offer"):
                print("[OFFER] receive offer: " + body_str)

                client_id = body.get("client_id")
                offer = RTCSessionDescription(sdp=body.get("body").get("sdp"), type=body.get("body").get("type"))

                pc = createPeerConnection()
                pcs.setdefault(client_id, pc)

                @pc.on("connectionstatechange")
                async def on_connectionstatechange():
                    print("Connection state is %s" % pc.connectionState)
                    if pc.connectionState == "failed" or pc.connectionState == "closed":
                        await pc.close()
                        pcs.pop(client_id)

                await pc.setRemoteDescription(offer)

                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)

                send_answer = stomper.send(f"/app/answer/{client_id}", json.dumps({"body": {"sdp": answer.sdp, "type": answer.type}}))
                await websocket.send(send_answer)


def createPeerConnection():
    global video

    # ice_server = RTCIceServer(
    #     urls = f"turn:{env.SERVER_URL}:3478",
    #     username = env.TURN_USERNAME,
    #     credential= env.TURN_PASSWORD
    # )
    pc = RTCPeerConnection(
        # configuration=RTCConfiguration(iceServers=[ice_server])
    )

    if video is None: 
        video = CustomVideoStreamTrack(0)

    if video:
        pc.addTrack(video)

    return pc


# 계속 실행되도록
asyncio.get_event_loop().run_until_complete(connect())