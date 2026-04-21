import threading
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode

from src.utils.global_logger import debug, info

# ✅ UI 서버가 저장하는 아티팩트 폴더와 유사한 개념으로, 로컬에서도 고정 경로 사용
ARTIFACTS_DIR = Path("./artifacts")      # 필요시 절대경로로
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

pipeline_options = PdfPipelineOptions()

# == 포트 5002 API 기본값과 동일하게 설정 ==
pipeline_options.do_ocr = True                    # do_ocr: true
pipeline_options.ocr_options.lang = []            # ocr_lang: [] (빈 배열)

# 테이블 관련 설정
pipeline_options.do_table_structure = True        # do_table_structure: true

# 이미지 관련 설정
pipeline_options.generate_picture_images = True   # include_images: true
pipeline_options.generate_page_images = True      # include_images: true
pipeline_options.images_scale = 2.0               # images_scale: 2.0


doc_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

# 🔒 Thread-safety: 전역 converter는 thread-safe하지 않으므로 락 사용
_converter_lock = threading.Lock()

def process_document(file_path: str):
    try:
        debug(f"📄 문서 처리 시작: {file_path}")
        # 🔒 Thread-safety: doc_converter는 thread-safe하지 않으므로 락 사용
        with _converter_lock:
            result = doc_converter.convert(file_path)
            doc = result.document
        debug("✅ 문서 변환 완료")
    except UnicodeDecodeError as e:
        raise Exception(f"문서 인코딩 오류: {str(e)}")
    except Exception as e:
        raise Exception(f"문서 처리 실패: {str(e)}")


    debug("📝 embedded 이미지 모드로 마크다운 생성 중...")
    markdown_result = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
    info(f"✅ embedded 마크다운 생성 완료: {len(markdown_result)} chars")
    
    # 📊 Docling 변환 결과 미리보기 (debug)
    preview_length = 500
    markdown_preview = markdown_result[:preview_length] + "..." if len(markdown_result) > preview_length else markdown_result
    debug(f"📄 [Docling 변환 결과 미리보기]\n{markdown_preview}")
    debug(f"📊 [Docling 통계] 총 길이: {len(markdown_result)} chars, 줄 수: {markdown_result.count(chr(10))} lines")

    return {"embedded_markdown": markdown_result}

if __name__ == "__main__":
    debug(process_document("test.pdf"))
