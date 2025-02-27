import logging
import os
from typing import Optional
from utils.settings import settings
from logging.handlers import RotatingFileHandler
import sys

def setup_logger(name: str, log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    로거 설정 함수: 콘솔과 파일에 로그 출력
    :param name: 로거 이름
    :param log_file: 로그 파일 경로 (기본값: settings.LOG_FILE)
    :param level: 로그 레벨 (기본값: INFO)
    :return: 설정된 로거 객체
    """
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 설정된 경우 중복 방지
    if logger.handlers:
        return logger
    
    # 로그 레벨 설정
    logger.setLevel(level)
    
    # 로그 포맷 설정
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 파일 핸들러 설정 (RotatingFileHandler로 파일 크기 관리)
    log_file = log_file or settings.LOG_FILE
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,              # 최대 5개 백업 파일
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except (OSError, ValueError) as e:
        # 파일 핸들러 설정 실패 시 경고 출력 후 콘솔로만 진행
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger(__name__).warning(f"🚨 로그 파일 설정 실패: {e}. 콘솔 로깅만 사용됩니다.")
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    
    # 로거 전파 비활성화 (상위 로거로 로그 전달 방지)
    logger.propagate = False
    
    return logger

# 테스트 코드
if __name__ == "__main__":
    # 기본 설정 테스트
    logger = setup_logger("TestLogger")
    logger.debug("디버그 메시지")
    logger.info("정보 메시지")
    logger.warning("경고 메시지")
    logger.error("오류 메시지")
    
    # 커스텀 설정 테스트
    custom_logger = setup_logger("CustomLogger", log_file="logs/custom.log", level=logging.DEBUG)
    custom_logger.debug("커스텀 디버그 메시지")
    custom_logger.info("커스텀 정보 메시지")