import logging

# 로깅 설정 및 logger 반환
def get_logger():    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger("WebRTC-Server")

logger = get_logger()