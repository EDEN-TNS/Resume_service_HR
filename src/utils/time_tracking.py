"""
시간 기록 및 성능 측정을 위한 모듈
"""
import os
import time
import pandas as pd
from datetime import datetime
from typing import Optional
from src.utils.global_logger import info, debug


class TimeTracker:
    """시간 측정 및 기록을 위한 클래스"""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.processing_start_time: Optional[float] = None
        self.ollama_time: float = 0.0
        self.markdown_length: int = 0
        self.token_count: int = 0
    
    def start_total_timer(self):
        """전체 처리 시작 시간 기록"""
        self.start_time = time.time()
        self.processing_start_time = time.time()
        self.ollama_time = 0.0
    
    def get_elapsed_time(self) -> float:
        """현재까지 경과 시간 반환"""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
    
    def set_ollama_time(self, ollama_time: float):
        """Ollama API 응답 시간 설정"""
        self.ollama_time = ollama_time
    
    def set_markdown_length(self, markdown_length: int):
        """마크다운 길이 설정"""
        self.markdown_length = markdown_length
    
    def set_token_count(self, token_count: int):
        """토큰 개수 설정"""
        self.token_count = token_count
    
    def get_processing_time(self) -> float:
        """문서 처리 시간 계산 (전체 시간 - Ollama 시간)"""
        total_time = self.get_elapsed_time()
        return total_time - self.ollama_time
    
    def print_timing_info(self, context: str = ""):
        """시간 정보 출력"""
        total_time = self.get_elapsed_time()
        processing_time = self.get_processing_time()
        
        prefix = f"[{context}] " if context else ""
        debug(f"📊 {prefix}전체 처리 시간: {total_time:.2f}초")
        debug(f"📊 {prefix}문서 처리 시간: {processing_time:.2f}초")
        debug(f"📊 {prefix}LLM API 응답 시간: {self.ollama_time:.2f}초")
        debug(f"📊 {prefix}마크다운 길이: {self.markdown_length:,}자")
        debug(f"📊 {prefix}토큰 개수: {self.token_count:,}개")


# def save_processing_time_to_excel(filename: str, total_time: float, ollama_time: float, processing_time: float, markdown_length: int = 0, token_count: int = 0):
#     """
#     파일 처리 시간을 Excel 파일에 기록하는 함수
#     """
#     try:
#         # processing_times 폴더 생성 (없으면)
#         processing_dir = "processing_times"
#         os.makedirs(processing_dir, exist_ok=True)
        
#         # 현재 날짜를 파일명에 추가
#         current_date = datetime.now().strftime("%Y%m%d")
#         excel_filename = f"processing_times_{current_date}.xlsx"
#         excel_path = os.path.join(processing_dir, excel_filename)
        
#         # 현재 시간
#         current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
#         # 새로운 데이터 행
#         new_data = {
#             '처리_시간': [current_time],
#             '원본_파일명': [filename],
#             '전체_처리_시간(초)': [round(total_time, 2)],
#             'Ollama_API_응답_시간(초)': [round(ollama_time, 2)],
#             '문서_처리_시간(초)': [round(processing_time, 2)],
#             '마크다운_길이(자)': [markdown_length],
#             '토큰_개수': [token_count]
#         }
        
#         # 기존 Excel 파일이 있는지 확인
#         if os.path.exists(excel_path):
#             # 기존 데이터 읽기
#             try:
#                 existing_df = pd.read_excel(excel_path)
#                 # 새 데이터 추가
#                 new_df = pd.DataFrame(new_data)
#                 combined_df = pd.concat([existing_df, new_df], ignore_index=True)
#             except Exception as e:
#                 print(f"기존 Excel 파일 읽기 실패, 새로 생성: {e}")
#                 combined_df = pd.DataFrame(new_data)
#         else:
#             # 새 파일 생성
#             combined_df = pd.DataFrame(new_data)
        
#         # Excel 파일로 저장
#         combined_df.to_excel(excel_path, index=False, engine='openpyxl')
#         print(f"✅ 처리 시간이 Excel 파일에 기록되었습니다: {excel_path}")
        
#     except Exception as e:
#         print(f"❌ Excel 파일 저장 실패: {e}")


def measure_ollama_response_time(func):
    """LLM API 응답 시간을 측정하는 데코레이터 (비동기 함수용)"""
    async def wrapper(*args, **kwargs):
        debug("LLM API 요청 시작")
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        debug("LLM API 요청 완료")
        info(f"🔍 [LLM] API 응답 시간: {elapsed_time:.2f}초")
        
        # 결과가 딕셔너리인 경우 elapsed_time 추가
        if isinstance(result, dict):
            result['elapsed_time'] = elapsed_time
        
        return result
    return wrapper


# def create_test_result_file(results: list, test_path: str, upload_url: str, successful: int, failed: int):
#     """테스트 결과를 파일로 저장하는 함수"""
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     result_file = f"upload_test_results_{timestamp}.txt"
    
#     with open(result_file, 'w', encoding='utf-8') as f:
#         f.write("파일 업로드 테스트 결과\n")
#         f.write(f"테스트 시간: {datetime.now().isoformat()}\n")
#         f.write(f"테스트 경로: {test_path}\n")
#         f.write(f"API URL: {upload_url}\n")
#         f.write(f"총 파일 수: {len(results)}\n")
#         f.write(f"성공: {successful}\n")
#         f.write(f"실패: {failed}\n\n")
        
#         f.write("상세 결과:\n")
#         for result in results:
#             processing_time = result.get('processing_time', 0)
#             f.write(f"- {result['filename']}: {result['status']} ({processing_time:.2f}초)\n")
#             if result['status'] != 'success':
#                 f.write(f"  오류: {result.get('error', 'Unknown')}\n")
    
#     print(f"\n📄 결과 저장: {result_file}")
#     return result_file


# 편의 함수들
def start_timer() -> TimeTracker:
    """새로운 TimeTracker 인스턴스를 생성하고 타이머를 시작"""
    tracker = TimeTracker()
    tracker.start_total_timer()
    return tracker


def print_timing_summary(tracker: TimeTracker, context: str = ""):
    """시간 요약 정보 출력"""
    tracker.print_timing_info(context)


# def save_timing_to_excel(tracker: TimeTracker, filename: str):
#     """TimeTracker의 시간 정보를 Excel에 저장"""
#     total_time = tracker.get_elapsed_time()
#     processing_time = tracker.get_processing_time()
#     save_processing_time_to_excel(filename, total_time, tracker.ollama_time, processing_time, tracker.markdown_length, tracker.token_count)
