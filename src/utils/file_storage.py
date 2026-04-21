"""
임시 파일 스토리지 유틸리티
Base64 오버헤드를 피하기 위해 파일을 디스크에 저장하고 경로만 전달
"""

import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from src.utils.global_logger import debug, warning, info


class FileStorage:
    """임시 파일 스토리지 관리 클래스"""
    
    def __init__(self, base_dir: Optional[str] = None, ttl_hours: int = 24):
        """
        Args:
            base_dir: 파일 저장 기본 디렉토리 (None이면 시스템 임시 디렉토리 사용)
            ttl_hours: 파일 보관 시간 (시간 단위, 기본 24시간)
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # 시스템 임시 디렉토리 사용
            self.base_dir = Path(tempfile.gettempdir()) / "docling_file_storage"
        
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        info(f"📁 파일 스토리지 초기화: {self.base_dir} (TTL: {ttl_hours}시간)")
    
    def save_file(self, file_data: bytes, task_id: str, filename: Optional[str] = None) -> str:
        """
        파일을 저장하고 경로 반환 (저장 후 검증 포함)
        단순 구조: file_storage/{uuid}.pdf 형태로 저장
        
        Args:
            file_data: 저장할 파일 데이터
            task_id: 작업 ID (메타데이터용, 경로에는 사용 안 함)
            filename: 원본 파일명 (확장자 추출용)
            
        Returns:
            저장된 파일의 절대 경로
            
        Raises:
            IOError: 파일 저장 실패 시
            ValueError: 저장 후 검증 실패 시
        """
        original_size = len(file_data)
        
        # 파일명 생성 (UUID로 고유성 보장)
        unique_id = str(uuid.uuid4())
        if filename:
            # 원본 파일명의 확장자 사용
            ext = Path(filename).suffix or ""
            storage_filename = f"{unique_id}{ext}"
        else:
            storage_filename = unique_id
        
        # 단순 구조: file_storage/{uuid}.pdf
        file_path = self.base_dir / storage_filename
        
        # 파일 저장
        try:
            with open(file_path, "wb") as f:
                f.write(file_data)
                # 파일 버퍼 플러시 보장 (디스크에 즉시 쓰기)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            error_msg = f"파일 저장 실패: {file_path}, 오류: {e}"
            warning(error_msg)
            raise IOError(error_msg) from e
        
        # 저장 후 검증: 파일 존재 및 크기 확인
        if not file_path.exists():
            error_msg = f"파일 저장 후 검증 실패: 파일이 존재하지 않음 - {file_path}"
            warning(error_msg)
            raise ValueError(error_msg)
        
        saved_size = file_path.stat().st_size
        if saved_size != original_size:
            error_msg = f"파일 저장 후 검증 실패: 크기 불일치 (원본: {original_size:,} bytes, 저장: {saved_size:,} bytes) - {file_path}"
            warning(error_msg)
            raise ValueError(error_msg)
        
        info(f"✅ 파일 저장 및 검증 완료: {file_path} ({saved_size:,} bytes, task_id: {task_id})")
        return str(file_path.absolute())
    
    def load_file(self, file_path: str) -> bytes:
        """
        저장된 파일 읽기
        
        Args:
            file_path: 파일 경로
            
        Returns:
            파일 데이터
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        with open(path, "rb") as f:
            data = f.read()
        
        debug(f"📖 파일 읽기 완료: {file_path} ({len(data):,} bytes)")
        return data
    
    def delete_file(self, file_path: str) -> bool:
        """
        파일 삭제
        
        Args:
            file_path: 삭제할 파일 경로
            
        Returns:
            삭제 성공 여부
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                # 디렉토리가 비어있으면 삭제
                parent_dir = path.parent
                if parent_dir.exists() and not any(parent_dir.iterdir()):
                    parent_dir.rmdir()
                debug(f"🗑️ 파일 삭제 완료: {file_path}")
                return True
            return False
        except Exception as e:
            warning(f"⚠️ 파일 삭제 실패: {file_path}, 오류: {e}")
            return False
    
    def delete_file_by_path(self, file_path: str) -> bool:
        """
        파일 경로로 파일 삭제
        
        Args:
            file_path: 삭제할 파일 경로
            
        Returns:
            삭제 성공 여부
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                info(f"🗑️ 파일 삭제 완료: {file_path}")
                return True
            return False
        except Exception as e:
            warning(f"⚠️ 파일 삭제 실패: {file_path}, 오류: {e}")
            return False
    
    def delete_task_files(self, task_id: str) -> bool:
        """
        특정 작업의 파일 삭제 (하위 호환성 유지)
        단순 구조에서는 file_path로 직접 삭제하므로 이 메서드는 사용되지 않음
        
        Args:
            task_id: 작업 ID (사용 안 함, 하위 호환성용)
            
        Returns:
            항상 True (실제 삭제는 delete_file_by_path 사용)
        """
        # 단순 구조에서는 task_id로 파일을 찾을 수 없으므로
        # 실제 삭제는 file_path로 직접 수행해야 함
        debug(f"ℹ️ delete_task_files 호출됨 (단순 구조에서는 사용 안 함): {task_id}")
        return True
    
    def cleanup_expired_files(self) -> int:
        """
        만료된 파일 정리 (TTL 기반, 24시간 이상 된 파일 삭제)
        
        Returns:
            삭제된 디렉토리 수
        """
        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(hours=self.ttl_hours)
        
        try:
            if not self.base_dir.exists():
                return 0
            
            # 단순 구조: file_storage/ 디렉토리 내의 모든 파일 확인
            for file_path in self.base_dir.iterdir():
                if file_path.is_dir():
                    # 디렉토리는 스킵 (하위 호환성)
                    continue
                
                if not file_path.is_file():
                    continue
                
                try:
                    # 파일 수정 시간 확인
                    file_stat = file_path.stat()
                    file_time = datetime.fromtimestamp(file_stat.st_mtime)
                    
                    # 24시간 이상 된 파일 삭제
                    if file_time < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                        debug(f"🗑️ 만료된 파일 삭제: {file_path} (생성: {file_time})")
                except (OSError, FileNotFoundError) as e:
                    # 파일이 이미 삭제되었거나 접근 불가능한 경우 스킵
                    warning(f"⚠️ 파일 확인 중 오류 (무시): {file_path}, {e}")
                    continue
        
        except Exception as e:
            warning(f"⚠️ 만료 파일 정리 중 오류: {e}")
        
        if deleted_count > 0:
            info(f"🧹 만료 파일 자동 정리 완료: {deleted_count}개 디렉토리 삭제 (TTL: {self.ttl_hours}시간)")
        
        return deleted_count


# 전역 파일 스토리지 인스턴스
_file_storage: Optional[FileStorage] = None


def get_file_storage() -> FileStorage:
    """전역 파일 스토리지 인스턴스 반환"""
    global _file_storage
    if _file_storage is None:
        storage_dir = os.getenv("FILE_STORAGE_DIR", None)
        ttl_hours = int(os.getenv("FILE_STORAGE_TTL_HOURS", "24"))
        _file_storage = FileStorage(base_dir=storage_dir, ttl_hours=ttl_hours)
    return _file_storage

