"""
전역 Logger 시스템

날짜별 로그 파일 생성 및 관리
engine/api 구분 및 인스턴스별 로그 분리
자동 로그 정리 (n년 보관)
"""

import logging
import os
import socket
import sys
import uuid
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from src.config.log_config import LogConfig


class GlobalLogger:
    """전역 로거 클래스"""
    
    _instance: Optional['GlobalLogger'] = None
    _logger: Optional[logging.Logger] = None
    _initialized: bool = False
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """로거 초기화 (한 번만 실행)"""
        if self._initialized:
            return
        
        # 설정 검증
        LogConfig.validate_config()
        
        # 인스턴스 ID 설정
        self.instance_id = self._get_instance_id()
        
        # 로거 설정
        self._setup_logger()
        
        # 초기화 완료
        self._initialized = True
        
        # 로거 시작 로그
        self._log_initialization()
    
    def _get_instance_id(self) -> str:
        """인스턴스 ID 생성"""
        if LogConfig.INSTANCE_ID:
            return LogConfig.INSTANCE_ID
        
        # 환경변수에서 컨테이너 ID 확인
        container_id = os.getenv("HOSTNAME")  # Docker 컨테이너의 경우 HOSTNAME이 컨테이너 ID
        if container_id:
            # 긴 컨테이너 ID는 앞 12자리만 사용
            return container_id[:12]
        
        # 호스트명 사용
        try:
            hostname = socket.gethostname()
            return hostname
        except Exception:
            pass
        
        # 마지막 수단: 랜덤 UUID
        return str(uuid.uuid4())[:8]
    
    def _setup_logger(self):
        """로거 설정"""
        # 로거 이름 생성: service_type.instance_id
        logger_name = f"{LogConfig.SERVICE_TYPE}.{self.instance_id}"
        self._logger = logging.getLogger(logger_name)
        
        # 로그 레벨 설정
        log_level = getattr(logging, LogConfig.LOG_LEVEL.upper())
        self._logger.setLevel(log_level)
        
        # 기존 핸들러 제거 (중복 방지)
        self._logger.handlers.clear()
        
        # 로그 포매터 설정
        formatter = self._get_formatter()
        
        # 파일 핸들러 추가
        self._add_file_handler(formatter)
        
        # 콘솔 핸들러 추가
        if LogConfig.CONSOLE_OUTPUT:
            self._add_console_handler(formatter)
        
        # 상위 로거로 전파 방지 (중복 로그 방지)
        self._logger.propagate = False
    
    def _get_formatter(self) -> logging.Formatter:
        """로그 포매터 생성"""
        # 포맷: [시간] [레벨] [서비스타입.인스턴스ID] 메시지
        log_format = (
            f"[%(asctime)s] [%(levelname)s] "
            f"[{LogConfig.SERVICE_TYPE}.{self.instance_id}] "
            f"%(message)s"
        )
        
        return logging.Formatter(
            log_format,
            datefmt=LogConfig.LOG_TIMESTAMP_FORMAT
        )
    
    def _add_file_handler(self, formatter: logging.Formatter):
        """파일 핸들러 추가 (날짜별 로테이션)"""
        # 로그 디렉토리 생성
        log_dir = LogConfig.get_service_log_directory()
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명: YYYY-MM-DD_service-type_instance-id.log
        # TimedRotatingFileHandler를 사용하여 자동으로 날짜별 파일 생성
        today = datetime.now().strftime(LogConfig.LOG_DATE_FORMAT)
        log_filename = f"{today}_{LogConfig.SERVICE_TYPE}_{self.instance_id}.log"
        log_filepath = log_dir / log_filename
        
        # 날짜별 로테이션 핸들러
        # midnight: 자정마다 새 파일 생성
        # backupCount: 보관할 파일 개수 (LOG_RETENTION_DAYS 일만큼)
        file_handler = TimedRotatingFileHandler(
            filename=str(log_filepath),
            when='midnight',
            interval=1,
            backupCount=LogConfig.LOG_RETENTION_DAYS,
            encoding=LogConfig.LOG_ENCODING,
            utc=False
        )
        
        # 로테이션 파일명 형식 설정
        file_handler.suffix = f"_{LogConfig.SERVICE_TYPE}_{self.instance_id}.log"
        file_handler.namer = self._custom_namer
        
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # 파일에는 모든 레벨 기록
        
        self._logger.addHandler(file_handler)
    
    def _custom_namer(self, default_name: str) -> str:
        """로테이션 파일명 커스터마이징"""
        # default_name: /path/to/logs/2025-11-10_api_xxx.log.2025-11-09_api_xxx.log
        # 원하는 형식: /path/to/logs/2025-11-09_api_xxx.log
        
        # 확장자 제거 및 날짜 추출
        base_dir = Path(default_name).parent
        parts = Path(default_name).name.split('.')
        
        if len(parts) >= 2:
            # 날짜 부분 추출 (parts[-2]가 날짜를 포함)
            rotated_filename = parts[-1]  # 예: 2025-11-09_api_xxx.log
            return str(base_dir / rotated_filename)
        
        return default_name
    
    def _add_console_handler(self, formatter: logging.Formatter):
        """콘솔 핸들러 추가"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # 콘솔에는 설정된 로그 레벨만 출력
        log_level = getattr(logging, LogConfig.LOG_LEVEL.upper())
        console_handler.setLevel(log_level)
        
        self._logger.addHandler(console_handler)
    
    def _log_initialization(self):
        """로거 초기화 로그"""
        config = LogConfig.get_config_summary()
        self.info("=" * 60)
        self.info("🚀 Global Logger Initialized")
        self.info(f"📂 Log Directory: {config['service_log_dir']}")
        self.info(f"🏷️  Service Type: {config['service_type']}")
        self.info(f"🆔 Instance ID: {config['instance_id']}")
        self.info(f"📊 Log Level: {config['log_level']}")
        self.info(f"📅 Retention: {config['retention_days']} days ({config['retention_years']} years)")
        self.info(f"💾 Max File Size: {config['max_file_size_mb']} MB")
        self.info(f"📝 Console Output: {config['console_output']}")
        self.info("=" * 60)
    
    def cleanup_old_logs(self):
        """오래된 로그 파일 정리"""
        try:
            log_dir = LogConfig.get_service_log_directory()
            if not log_dir.exists():
                return
            
            # 현재 시간
            now = datetime.now()
            cutoff_date = now - timedelta(days=LogConfig.LOG_RETENTION_DAYS)
            
            deleted_count = 0
            for log_file in log_dir.glob("*.log"):
                # 파일명에서 날짜 추출 (YYYY-MM-DD 형식)
                try:
                    filename = log_file.stem
                    date_str = filename.split('_')[0]  # 첫 부분이 날짜
                    file_date = datetime.strptime(date_str, LogConfig.LOG_DATE_FORMAT)
                    
                    # 보관 기간 초과 파일 삭제
                    if file_date < cutoff_date:
                        log_file.unlink()
                        deleted_count += 1
                        self.debug(f"🗑️  Deleted old log file: {log_file.name}")
                
                except (ValueError, IndexError):
                    # 날짜 파싱 실패 시 무시
                    continue
            
            if deleted_count > 0:
                self.info(f"🧹 Cleaned up {deleted_count} old log files")
        
        except Exception as e:
            self.error(f"❌ Failed to cleanup old logs: {e}")
    
    # 로깅 메서드
    def debug(self, message: str):
        """디버그 로그"""
        if self._logger:
            self._logger.debug(message)
    
    def info(self, message: str):
        """정보 로그"""
        if self._logger:
            self._logger.info(message)
    
    def warning(self, message: str):
        """경고 로그"""
        if self._logger:
            self._logger.warning(message)
    
    def error(self, message: str):
        """에러 로그"""
        if self._logger:
            self._logger.error(message)
    
    def critical(self, message: str):
        """치명적 에러 로그"""
        if self._logger:
            self._logger.critical(message)
    
    def exception(self, message: str):
        """예외 로그 (스택 트레이스 포함)"""
        if self._logger:
            self._logger.exception(message)
    
    @property
    def logger(self) -> logging.Logger:
        """내부 logger 객체 반환"""
        return self._logger


# 전역 로거 인스턴스
global_logger = GlobalLogger()


# 편의 함수들
def get_logger() -> GlobalLogger:
    """전역 로거 인스턴스 반환"""
    return global_logger


def debug(message: str):
    """디버그 로그"""
    global_logger.debug(message)


def info(message: str):
    """정보 로그"""
    global_logger.info(message)


def warning(message: str):
    """경고 로그"""
    global_logger.warning(message)


def error(message: str):
    """에러 로그"""
    global_logger.error(message)


def critical(message: str):
    """치명적 에러 로그"""
    global_logger.critical(message)


def exception(message: str):
    """예외 로그"""
    global_logger.exception(message)

