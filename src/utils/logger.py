"""
디버그 로깅 시스템
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class DebugLogger:
    """디버그 로깅을 위한 클래스"""
    
    def __init__(self):
        self.debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
        self.log_dir = Path("debug_logs")
        if self.debug_mode:
            self.log_dir.mkdir(exist_ok=True)
    
    def is_debug(self) -> bool:
        """디버그 모드인지 확인"""
        return self.debug_mode
    
    def debug_print(self, message: str, emoji: str = "🔍"):
        """디버그 모드일 때만 출력"""
        if self.debug_mode:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"{emoji} [{timestamp}] {message}")
    
    def save_debug_data(self, filename: str, data: Any, description: str = ""):
        """디버그 데이터를 파일로 저장"""
        if not self.debug_mode:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        file_path = self.log_dir / safe_filename
        
        try:
            if isinstance(data, (dict, list)):
                with open(file_path.with_suffix('.json'), 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(file_path.with_suffix('.txt'), 'w', encoding='utf-8') as f:
                    f.write(str(data))
            
            if description:
                self.debug_print(f"💾 {description}: {file_path}")
            
        except Exception as e:
            self.debug_print(f"❌ 디버그 파일 저장 실패: {e}")
    
    def log_step(self, step_number: int, step_name: str, data: Any = None):
        """단계별 로깅"""
        if not self.debug_mode:
            return
        
        self.debug_print(f"📍 단계 {step_number}: {step_name}")
        
        if data is not None:
            if isinstance(data, str) and len(data) > 200:
                # 긴 텍스트는 일부만 출력하고 파일로 저장
                preview = data[:200] + "..."
                self.debug_print(f"   📄 데이터 미리보기: {preview}")
                self.save_debug_data(
                    f"step{step_number}_{step_name.lower().replace(' ', '_')}", 
                    data,
                    f"단계 {step_number} 데이터"
                )
            else:
                self.debug_print(f"   📊 데이터: {data}")


# 전역 로거 인스턴스
debug_logger = DebugLogger()