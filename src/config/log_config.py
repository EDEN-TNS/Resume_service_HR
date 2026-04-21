"""
로그 시스템 설정
"""

import os
from pathlib import Path
from typing import Optional


class LogConfig:
    """로그 시스템 전역 설정"""
    
    # 로그 디렉토리 기본 경로
    BASE_LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    
    # 로그 보관 기간 (일 단위)
    # 기본값: 365일 (1년), 환경변수로 n년 설정 가능
    LOG_RETENTION_DAYS: int = int(os.getenv("LOG_RETENTION_DAYS", "365"))
    
    # 로그 파일명 형식
    LOG_DATE_FORMAT: str = "%Y-%m-%d"  # 파일명에 사용될 날짜 형식
    LOG_TIMESTAMP_FORMAT: str = "%Y-%m-%d %H:%M:%S"  # 로그 메시지에 사용될 시간 형식
    
    # 서비스 타입 (api 또는 engine)
    SERVICE_TYPE: str = os.getenv("SERVICE_TYPE", "unknown")
    
    # 인스턴스 식별자 (컨테이너 ID, 호스트명 등)
    # 기본적으로 호스트명 사용, 없으면 랜덤 UUID 생성
    INSTANCE_ID: Optional[str] = os.getenv("INSTANCE_ID", None)
    
    # 로그 레벨
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # 콘솔 출력 여부
    CONSOLE_OUTPUT: bool = os.getenv("CONSOLE_OUTPUT", "true").lower() == "true"
    
    # 로그 파일 최대 크기 (바이트) - 기본 100MB
    MAX_LOG_FILE_SIZE: int = int(os.getenv("MAX_LOG_FILE_SIZE", str(100 * 1024 * 1024)))
    
    # 로그 파일 백업 개수
    BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    
    # 로그 인코딩
    LOG_ENCODING: str = "utf-8"
    
    @classmethod
    def get_log_directory(cls) -> Path:
        """로그 디렉토리 경로 반환"""
        return Path(cls.BASE_LOG_DIR)
    
    @classmethod
    def get_service_log_directory(cls) -> Path:
        """서비스별 로그 디렉토리 경로 반환"""
        return cls.get_log_directory() / cls.SERVICE_TYPE
    
    @classmethod
    def validate_config(cls) -> bool:
        """설정 유효성 검사"""
        try:
            # 로그 디렉토리 생성
            log_dir = cls.get_service_log_directory()
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 로그 레벨 검증
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if cls.LOG_LEVEL.upper() not in valid_levels:
                print(f"⚠️ Invalid LOG_LEVEL: {cls.LOG_LEVEL}, defaulting to INFO")
                cls.LOG_LEVEL = "INFO"
            
            # 보관 기간 검증
            if cls.LOG_RETENTION_DAYS < 1:
                print(f"⚠️ Invalid LOG_RETENTION_DAYS: {cls.LOG_RETENTION_DAYS}, defaulting to 365")
                cls.LOG_RETENTION_DAYS = 365
            
            return True
            
        except Exception as e:
            print(f"❌ Log config validation failed: {e}")
            return False
    
    @classmethod
    def get_config_summary(cls) -> dict:
        """설정 요약 정보 반환"""
        return {
            "base_log_dir": str(cls.get_log_directory()),
            "service_log_dir": str(cls.get_service_log_directory()),
            "retention_days": cls.LOG_RETENTION_DAYS,
            "retention_years": round(cls.LOG_RETENTION_DAYS / 365, 2),
            "service_type": cls.SERVICE_TYPE,
            "instance_id": cls.INSTANCE_ID,
            "log_level": cls.LOG_LEVEL,
            "console_output": cls.CONSOLE_OUTPUT,
            "max_file_size_mb": cls.MAX_LOG_FILE_SIZE / (1024 * 1024),
            "backup_count": cls.BACKUP_COUNT,
        }

