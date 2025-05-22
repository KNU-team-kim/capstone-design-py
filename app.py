from core.signaling import execute
from util.my_logger import logger
from core.webrtc import cleanup
from dotenv import load_dotenv
import asyncio

load_dotenv()

# 메인 함수
async def main():
    try:
        logger.info("WebRTC 서버 시작 - 색상 로깅 기능 활성화")
        logger.info("10초마다 색상이 변경됩니다: RED -> GREEN -> BLUE -> RED ...")
        await execute()
    except KeyboardInterrupt:
        logger.info("키보드 인터럽트로 프로그램 종료")
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {str(e)}")
    finally:
        await cleanup()

# 애플리케이션 실행
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("프로그램이 강제로 종료되었습니다.")