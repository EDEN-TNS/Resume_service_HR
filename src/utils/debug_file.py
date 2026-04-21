"""
디버깅을 위한 파일 저장 및 로깅 유틸리티
"""

import json
import os
from typing import Any, Dict, Optional
from datetime import datetime
from src.utils.global_logger import info, warning


class DebugFileManager:
    """디버깅 파일 관리 클래스"""
    
    def __init__(self, base_output_dir: str = "markdown_result/debug"):
        self.base_output_dir = base_output_dir
        self.debug_enabled = False  # 디버깅 모드 활성화/비활성화
    
    def save_json_result(self, data: Dict[str, Any], filename: str, subdir: str = "json") -> Optional[str]:
        """
        JSON 결과를 파일로 저장
        
        Args:
            data: 저장할 데이터
            filename: 원본 파일명
            subdir: 하위 디렉토리 (기본값: "json")
            
        Returns:
            저장된 파일 경로 또는 None
        """
        if not self.debug_enabled:
            return None
            
        try:
            output_dir = os.path.join(self.base_output_dir, subdir)
            os.makedirs(output_dir, exist_ok=True)
            
            base_filename = os.path.splitext(filename)[0]
            json_path = os.path.join(output_dir, f"{base_filename}.json")
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            info(f"✅ JSON 결과 저장 완료: {json_path}")
            return json_path
            
        except Exception as e:
            warning(f"❌ JSON 결과 저장 실패: {e}")
            return None
    
    def save_markdown_result(self, content: str, filename: str, suffix: str = "", header: str = "", subdir: str = "md") -> Optional[str]:
        """
        마크다운 결과를 파일로 저장
        
        Args:
            content: 저장할 마크다운 내용
            filename: 원본 파일명
            suffix: 파일명 접미사
            header: 파일 상단에 추가할 헤더
            subdir: 하위 디렉토리 (기본값: "md")
            
        Returns:
            저장된 파일 경로 또는 None
        """
        if not self.debug_enabled:
            return None
            
        try:
            output_dir = os.path.join(self.base_output_dir, subdir)
            os.makedirs(output_dir, exist_ok=True)
            
            base_filename = os.path.splitext(filename)[0]
            output_filename = f"{base_filename}{suffix}.md"
            output_path = os.path.join(output_dir, output_filename)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(header + content)
            
            info(f"✅ 마크다운 저장 완료: {output_path}")
            return output_path
            
        except Exception as e:
            warning(f"❌ 마크다운 저장 실패: {e}")
            return None
    
    # def save_processing_log(self, log_data: Dict[str, Any], filename: str) -> Optional[str]:
    #     """
    #     처리 과정 로그를 파일로 저장
        
    #     Args:
    #         log_data: 로그 데이터
    #         filename: 원본 파일명
            
    #     Returns:
    #         저장된 파일 경로 또는 None
    #     """
    #     if not self.debug_enabled:
    #         return None
            
    #     try:
    #         output_dir = os.path.join(self.base_output_dir, "logs")
    #         os.makedirs(output_dir, exist_ok=True)
            
    #         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #         base_filename = os.path.splitext(filename)[0]
    #         log_path = os.path.join(output_dir, f"{base_filename}_{timestamp}.log")
            
    #         with open(log_path, "w", encoding="utf-8") as f:
    #             json.dump(log_data, f, ensure_ascii=False, indent=2)
            
    #         print(f"✅ 처리 로그 저장 완료: {log_path}")
    #         return log_path
            
    #     except Exception as e:
    #         print(f"❌ 처리 로그 저장 실패: {e}")
    #         return None
    
    # def save_error_log(self, error_data: Dict[str, Any], filename: str) -> Optional[str]:
    #     """
    #     에러 로그를 파일로 저장
        
    #     Args:
    #         error_data: 에러 데이터
    #         filename: 원본 파일명
            
    #     Returns:
    #         저장된 파일 경로 또는 None
    #     """
    #     if not self.debug_enabled:
    #         return None
            
    #     try:
    #         output_dir = os.path.join(self.base_output_dir, "errors")
    #         os.makedirs(output_dir, exist_ok=True)
            
    #         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #         base_filename = os.path.splitext(filename)[0]
    #         error_path = os.path.join(output_dir, f"{base_filename}_error_{timestamp}.json")
            
    #         with open(error_path, "w", encoding="utf-8") as f:
    #             json.dump(error_data, f, ensure_ascii=False, indent=2)
            
    #         print(f"✅ 에러 로그 저장 완료: {error_path}")
    #         return error_path
            
    #     except Exception as e:
    #         print(f"❌ 에러 로그 저장 실패: {e}")
    #         return None
    
    def set_debug_mode(self, enabled: bool) -> None:
        """디버깅 모드 설정"""
        self.debug_enabled = enabled
        info(f"디버깅 모드: {'활성화' if enabled else '비활성화'}")
    
    def get_output_directory(self, subdir: str = "") -> str:
        """출력 디렉토리 경로 반환"""
        if subdir:
            return os.path.join(self.base_output_dir, subdir)
        return self.base_output_dir


# 전역 디버그 매니저 인스턴스
debug_manager = DebugFileManager()


# 편의 함수들
def save_json_result(data: Dict[str, Any], filename: str, subdir: str = "json") -> Optional[str]:
    """JSON 결과 저장 (편의 함수)"""
    return debug_manager.save_json_result(data, filename, subdir)


def save_markdown_result(content: str, filename: str, suffix: str = "", header: str = "", subdir: str = "md") -> Optional[str]:
    """마크다운 결과 저장 (편의 함수)"""
    return debug_manager.save_markdown_result(content, filename, suffix, header, subdir)


# def save_processing_log(log_data: Dict[str, Any], filename: str) -> Optional[str]:
#     """처리 로그 저장 (편의 함수)"""
#     return debug_manager.save_processing_log(log_data, filename)


# def save_error_log(error_data: Dict[str, Any], filename: str) -> Optional[str]:
#     """에러 로그 저장 (편의 함수)"""
#     return debug_manager.save_error_log(error_data, filename)


def set_debug_mode(enabled: bool) -> None:
    """디버깅 모드 설정 (편의 함수)"""
    debug_manager.set_debug_mode(enabled)
