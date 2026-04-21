"""
파일 검증 유틸리티
DoS 및 인젝션 공격 방지를 위한 파일 검증 기능 제공
"""

import os
import re
from pathlib import Path
from typing import Optional, Set

from fastapi import HTTPException, UploadFile

from src.utils.global_logger import error, info


class FileValidationError(Exception):
    """파일 검증 오류"""
    pass


class FileValidator:
    """파일 검증 클래스"""
    
    # 허용된 파일 확장자 (소문자로 정규화)
    ALLOWED_EXTENSIONS: Set[str] = {
        # 문서 형식
        '.pdf', '.doc', '.docx', '.txt', '.rtf', '.pptx',
        # 이미지 형식
        '.jpg', '.jpeg', '.png', '.gif', '.bmp'
    }
    
    # 최대 파일 크기 (바이트 단위, 기본값: 100MB)
    DEFAULT_MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    # 최대 파일명 길이
    MAX_FILENAME_LENGTH: int = 255
    
    # 금지된 파일명 패턴 (경로 탐색, 특수 문자 등)
    FORBIDDEN_PATTERNS: list = [
        r'\.\.',  # 경로 탐색 (..)
        r'/',     # 슬래시
        r'\\',    # 백슬래시
        r'[<>:"|?*]',  # Windows 금지 문자
        r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',  # Windows 예약 이름
    ]
    
    def __init__(
        self,
        allowed_extensions: Optional[Set[str]] = None,
        max_file_size: Optional[int] = None
    ):
        """
        Args:
            allowed_extensions: 허용된 파일 확장자 집합 (None이면 기본값 사용)
            max_file_size: 최대 파일 크기 (바이트, None이면 기본값 사용)
        """
        self.allowed_extensions = allowed_extensions or self.ALLOWED_EXTENSIONS
        # 소문자로 정규화
        self.allowed_extensions = {ext.lower() for ext in self.allowed_extensions}
        self.max_file_size = max_file_size or self.DEFAULT_MAX_FILE_SIZE
    
    def validate_filename(self, filename: Optional[str]) -> str:
        """
        파일명 검증
        
        Args:
            filename: 검증할 파일명
            
        Returns:
            정규화된 파일명
            
        Raises:
            FileValidationError: 파일명이 유효하지 않은 경우
        """
        if not filename or not filename.strip():
            raise FileValidationError("파일명이 비어있습니다.")
        
        filename = filename.strip()
        
        # 파일명 길이 검증
        if len(filename) > self.MAX_FILENAME_LENGTH:
            error(f"❌ [검증 실패] 파일명 길이 초과: {len(filename)}자 (최대: {self.MAX_FILENAME_LENGTH}자)")
            raise FileValidationError(
                f"파일명이 너무 깁니다. (최대 {self.MAX_FILENAME_LENGTH}자, 현재: {len(filename)}자)"
            )
        
        # 금지된 패턴 검증
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                error(f"❌ [검증 실패] 파일명에 금지된 패턴 발견: 패턴='{pattern}', 파일명='{filename}'")
                raise FileValidationError(
                    f"파일명에 허용되지 않은 문자가 포함되어 있습니다: {filename}"
                )
        
        # 파일명 정규화 (경로 분리)
        normalized_name = os.path.basename(filename)
        
        # 빈 파일명 체크 (경로만 있는 경우)
        if not normalized_name or normalized_name == '.' or normalized_name == '..':
            error(f"❌ [검증 실패] 유효하지 않은 파일명: '{normalized_name}'")
            raise FileValidationError("유효하지 않은 파일명입니다.")
        
        return normalized_name
    
    def validate_extension(self, filename: str) -> str:
        """
        파일 확장자 검증
        
        Args:
            filename: 파일명
            
        Returns:
            소문자로 정규화된 확장자
            
        Raises:
            FileValidationError: 확장자가 허용되지 않은 경우
        """
        path = Path(filename)
        extension = path.suffix.lower()
        
        if not extension:
            error(f"❌ [검증 실패] 확장자 없음: 파일명='{filename}'")
            raise FileValidationError("파일 확장자가 없습니다.")
        
        if extension not in self.allowed_extensions:
            allowed_list = ', '.join(sorted(self.allowed_extensions))
            error(f"❌ [검증 실패] 허용되지 않은 확장자: 확장자='{extension}', 허용 목록=[{allowed_list}]")
            raise FileValidationError(
                f"허용되지 않은 파일 형식입니다. (확장자: {extension}, 허용된 형식: {allowed_list})"
            )
        
        return extension
    
    def validate_file_size(self, file_size: int) -> None:
        """
        파일 크기 검증
        
        Args:
            file_size: 파일 크기 (바이트)
            
        Raises:
            FileValidationError: 파일 크기가 제한을 초과한 경우
        """
        file_size_mb = file_size / (1024 * 1024)
        max_size_mb = self.max_file_size / (1024 * 1024)
        
        if file_size <= 0:
            error(f"❌ [검증 실패] 파일 크기 0: 크기={file_size} bytes")
            raise FileValidationError("파일 크기가 0입니다.")
        
        if file_size > self.max_file_size:
            error(f"❌ [검증 실패] 파일 크기 초과: 크기={file_size_mb:.2f}MB, 최대={max_size_mb:.1f}MB")
            raise FileValidationError(
                f"파일 크기가 제한을 초과했습니다. (최대: {max_size_mb:.1f}MB, 현재: {file_size_mb:.1f}MB)"
            )
    
    async def validate_upload_file(self, file: UploadFile) -> dict:
        """
        업로드 파일 전체 검증
        
        Args:
            file: FastAPI UploadFile 객체
            
        Returns:
            검증 정보 딕셔너리:
            {
                'filename': 정규화된 파일명,
                'extension': 확장자,
                'size': 파일 크기,
                'content_type': MIME 타입
            }
            
        Raises:
            HTTPException: 검증 실패 시
        """
        original_filename = file.filename or "unknown"
        info(f"🔍 [검증 시작] 파일 검증 시작: 파일명='{original_filename}', Content-Type='{file.content_type}'")
        
        try:
            # 1. 파일명 검증
            if not file.filename:
                error("❌ [검증 실패] 파일명이 제공되지 않음")
                raise FileValidationError("파일명이 제공되지 않았습니다.")
            
            normalized_filename = self.validate_filename(file.filename)
            
            # 2. 확장자 검증
            extension = self.validate_extension(normalized_filename)
            
            # 3. 파일 크기 검증 (파일을 읽기 전에 크기 확인)
            # FastAPI UploadFile은 스트림이므로, 파일을 읽어야 크기를 알 수 있음
            # 하지만 여기서는 파일을 읽지 않고 검증만 수행
            # 실제 크기 검증은 파일을 읽은 후 수행해야 함
            
            validation_result = {
                'filename': normalized_filename,
                'extension': extension,
                'content_type': file.content_type
            }
            
            info(f"✅ [검증 완료] 파일 검증 성공: 파일명='{normalized_filename}', 확장자='{extension}', Content-Type='{file.content_type}'")
            return validation_result
            
        except FileValidationError as e:
            error(f"❌ [검증 실패] 파일 검증 오류: {str(e)}, 원본 파일명='{original_filename}'")
            raise HTTPException(
                status_code=400,
                detail=f"파일 검증 실패: {str(e)}"
            )
        except Exception as e:
            error(f"❌ [검증 오류] 예상치 못한 오류: {str(e)}, 원본 파일명='{original_filename}'")
            raise HTTPException(
                status_code=400,
                detail=f"파일 검증 중 오류가 발생했습니다: {str(e)}"
            )
    
    def validate_file_content(self, file_content: bytes, filename: str) -> None:
        """
        파일 내용 검증 (크기 포함)
        
        Args:
            file_content: 파일 내용 (바이트)
            filename: 파일명 (로깅용)
            
        Raises:
            HTTPException: 검증 실패 시
        """
        try:
            # 파일 크기 검증
            self.validate_file_size(len(file_content))
            
        except FileValidationError as e:
            error(f"❌ [검증 실패] 파일 내용 검증 오류: {str(e)}, 파일명='{filename}', 크기={len(file_content):,} bytes")
            raise HTTPException(
                status_code=400,
                detail=f"파일 검증 실패: {str(e)}"
            )
        except Exception as e:
            error(f"❌ [검증 오류] 예상치 못한 오류: {str(e)}, 파일명='{filename}'")
            raise HTTPException(
                status_code=400,
                detail=f"파일 검증 중 오류가 발생했습니다: {str(e)}"
            )


# 전역 파일 검증기 인스턴스
_file_validator: Optional[FileValidator] = None


def get_file_validator() -> FileValidator:
    """
    전역 파일 검증기 인스턴스 반환
    
    환경 변수:
        ALLOWED_EXTENSIONS: 허용된 확장자 목록 (쉼표로 구분, 예: ".pdf,.docx,.jpg")
        MAX_FILE_SIZE_MB: 최대 파일 크기 (MB 단위, 기본값: 100MB)
    """
    global _file_validator
    
    if _file_validator is None:
        # 환경 변수에서 설정 읽기
        allowed_extensions_str = os.getenv("ALLOWED_EXTENSIONS", None)
        allowed_extensions = None
        
        if allowed_extensions_str:
            extensions = {ext.strip().lower() for ext in allowed_extensions_str.split(',') if ext.strip()}
            if extensions:
                allowed_extensions = extensions
        
        max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
        max_file_size = max_file_size_mb * 1024 * 1024
        
        _file_validator = FileValidator(
            allowed_extensions=allowed_extensions,
            max_file_size=max_file_size
        )
    
    return _file_validator

