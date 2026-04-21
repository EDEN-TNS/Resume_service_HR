import os
import shutil
import subprocess
import tempfile
import time
from typing import Dict, Tuple, Optional
from fastapi import UploadFile
from PIL import Image
import pdfplumber
import pypdf

from src.document_processing.docling_processing import process_document
from src.document_processing.ocr_processing import _safe_ocr, inject_image_ocr
from src.document_processing.remember_format import extract_remember
from src.document_processing.detect_genre import detect_genre
from src.text_processing.text_preprocessing_ko import remove_long_paragraphs_by_sentences_ocr
from src.text_processing.text_preprocessing_eng import remove_sections_journal, extract_sections_journal_result
from src.text_processing.text_preprocessing_ko import extract_sections_korean_result, remove_sections_korean
from src.utils.debug_file import save_markdown_result
from src.utils.global_logger import info, debug, warning, error


def convert_doc_to_docx(input_path: str) -> str:
    """
    Convert .doc file to .docx using LibreOffice
    Returns the path to the converted .docx file
    """
    try:
        # Create output directory for converted file
        output_dir = os.path.dirname(input_path)
        output_path = os.path.join(
            output_dir, os.path.splitext(os.path.basename(input_path))[0] + ".docx"
        )

        # LibreOffice command to convert .doc to .docx
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to",
            "docx",
            "--outdir",
            output_dir,
            input_path,
        ]

        # Run the conversion
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return output_path
        else:
            raise Exception(f"LibreOffice conversion failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        raise Exception("LibreOffice conversion timed out")
    except Exception as e:
        raise Exception(f"Error converting .doc to .docx: {str(e)}")


def remove_pdf_password(input_path, password="careers2024"):
    """PDF에서 패스워드를 제거하여 새로운 PDF 생성"""
    try:
        with open(input_path, 'rb') as file:
            reader = pypdf.PdfReader(file)
            
            if not reader.is_encrypted:
                return input_path
            
            if reader.decrypt(password) == 0:
                return input_path
            
            temp_path = input_path.replace('.pdf', '_unencrypted.pdf')
            writer = pypdf.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            
            with open(temp_path, 'wb') as output_file:
                writer.write(output_file)
            
            return temp_path
            
    except Exception as e:
        warning(f"⚠️ 패스워드 제거 실패: {str(e)}")
        return input_path


class DocumentPreprocessor:
    """문서 전처리를 담당하는 클래스"""
    
    def __init__(self):
        self.temp_files = []  # 정리할 임시 파일들 추적
        self.saved_files = []  # 보존할 저장용 파일들 추적
        self.temp_dirs = []  # 정리할 임시 디렉토리들 추적
    
    def preprocess_document(self, file: UploadFile) -> Tuple[str, str, Optional[Dict], Optional[Dict]]:
        """
        문서를 전처리하고 마크다운 텍스트를 반환
        
        Args:
            file: 업로드된 파일
            
        Returns:
            Tuple[str, str, Optional[Dict], Optional[Dict]]: (processed_markdown, genre, remember_result, sections_journal_result)
        """
        try:
            # 1. 임시 파일 생성
            temp_file_path = self._create_temp_file(file)
            
            # 2. 파일 변환 (.doc → .docx → .pdf)
            converted_file_path = self._convert_file(temp_file_path, file.filename)
            
            # 3. PDF 패스워드 제거
            unencrypted_pdf_path = self._remove_pdf_password(converted_file_path)
            
            # 4. 문서 처리 (docling)
            processed_markdown, genre, remember_result = self._process_document_content(
                unencrypted_pdf_path, file.filename
            )
            
            # 5. 텍스트 전처리(OCR)
            final_markdown, sections_journal_result = self._post_process_text(processed_markdown, genre, file.filename)
            
            return final_markdown, genre, remember_result, sections_journal_result
            
        except Exception as e:
            error(f"❌ 문서 전처리 중 오류 발생: {str(e)}")
            raise e
        finally:
            # 임시 파일 정리
            self._cleanup_temp_files()
    
    def _create_temp_file(self, file: UploadFile) -> str:
        """업로드된 파일을 임시 파일로 저장"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            file_content = file.file.read()
            temp_file.write(file_content)
            temp_file_path = temp_file.name
            self.temp_files.append(temp_file_path)
            return temp_file_path
    
    def _convert_file(self, temp_file_path: str, filename: str) -> str:
        """파일 형식 변환 (.doc → .docx → .pdf)"""
        file_extension = os.path.splitext(filename)[1].lower()
        converted_file_path = temp_file_path
        
        # .doc → .docx 변환
        if file_extension == ".doc":
            try:
                converted_file_path = convert_doc_to_docx(temp_file_path)
                os.unlink(temp_file_path)
                self.temp_files.append(converted_file_path)
                debug(f"📄 DOC to DOCX 변환 완료: {converted_file_path}")
            except Exception as e:
                warning(f"⚠️ Could not convert .doc to .docx: {str(e)}")
                converted_file_path = temp_file_path
        
        # .docx → .pdf 변환
        if file_extension == ".docx" or (os.path.splitext(converted_file_path)[1].lower() == ".docx"):
            try:
                temp_pdf_dir = "./tmp"
                os.makedirs(temp_pdf_dir, exist_ok=True)
                pdf_path = os.path.join(
                    temp_pdf_dir,
                    os.path.splitext(os.path.basename(converted_file_path))[0] + ".pdf"
                )
                
                # LibreOffice로 docx를 pdf로 변환
                cmd = [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    temp_pdf_dir,
                    converted_file_path,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    converted_file_path = pdf_path
                    self.temp_files.append(converted_file_path)
                    info(f"📄 DOCX to PDF 변환 완료: {pdf_path}")
                else:
                    warning(f"⚠️ Could not convert .docx to .pdf: {result.stderr}")
            except Exception as e:
                warning(f"⚠️ Could not convert .docx to .pdf: {str(e)}")
        
        return converted_file_path
    
    def _remove_pdf_password(self, file_path: str) -> str:
        """PDF 패스워드 제거"""
        if file_path.lower().endswith(".pdf"):
            debug("🔐 PDF 파일 감지, 비밀번호 제거 시도")
            unencrypted_pdf_path = remove_pdf_password(file_path)
            if unencrypted_pdf_path != file_path:
                self.temp_files.append(unencrypted_pdf_path)
            return unencrypted_pdf_path
        else:
            debug("✅ 비밀번호 없음")
            return file_path
    
    def _process_document_content(self, file_path: str, filename: str) -> Tuple[str, str, Optional[Dict]]:
        """문서 내용 처리 (genre 감지, remember 형식 처리, 일반 문서 처리)"""
        genre = "default"
        remember_result = None
        
        if file_path.lower().endswith(".pdf"):
            try:
                # Genre 감지
                genre = self._detect_genre(file_path)
                info(f"📋 감지된 genre: {genre}")
                
                # Remember 형식 처리
                if genre == "remember":
                    remember_result = self._process_remember_format(file_path, filename)
                    if remember_result and "image_paths" in remember_result:
                        processed_markdown = self._process_remember_ocr(remember_result, filename)
                        return processed_markdown, genre, remember_result
                    else:
                        warning("⚠️ OCR 텍스트 추출 실패")
                        return "", genre, remember_result
                
            except Exception as api_error:
                warning(f"⚠️ PDF 처리 실패, 기존 방식으로 진행: {str(api_error)}")
        
        # 일반 문서 처리
        processed_markdown = self._process_regular_document(file_path)
        return processed_markdown, genre, remember_result
    
    def _detect_genre(self, file_path: str) -> str:
        """문서 형식 감지"""
        class FileWrapper:
            def __init__(self, file_path):
                self.filename = os.path.basename(file_path)
                self.file = open(file_path, 'rb')
        
        file_wrapper = FileWrapper(file_path)
        pdf = pdfplumber.open(file_wrapper.file)
        genre = detect_genre(pdf)
        pdf.close()
        file_wrapper.file.close()
        
        return genre
    
    def _process_remember_format(self, file_path: str, filename: str) -> Optional[Dict]:
        """Remember 형식 문서 처리"""
        import uuid
        # 파일명과 UUID를 조합하여 고유 식별자 생성
        # 파일명에서 확장자 제거하고 안전한 문자열로 변환
        safe_filename = os.path.splitext(filename)[0].replace(" ", "_").replace("/", "_")
        unique_id = f"{safe_filename}_{uuid.uuid4().hex[:8]}"
        
        # 이미지 저장 디렉토리 경로 생성 및 추적 (예외 발생 전에 추가)
        image_dir = os.path.join("/app/images", unique_id)
        self.temp_dirs.append(image_dir)
        
        try:
            pdf = pdfplumber.open(file_path)
            remember_result = extract_remember(pdf, unique_id=unique_id)
            pdf.close()
            return remember_result
        except Exception as e:
            # 예외 발생 시에도 temp_dirs에 추가되어 cleanup에서 정리됨
            print(f"Remember 형식 처리 중 오류 발생: {str(e)}")
            raise
    
    def _process_remember_ocr(self, remember_result: Dict, filename: str) -> str:
        """Remember 형식의 이미지들을 OCR로 처리"""
        info("📷 Remember 형식 감지됨, 이미지 OCR 처리 시작")
        
        text_with_ocr = ""
        opened_images = []  # 열린 이미지 추적
        
        try:
            for image_path in remember_result["image_paths"]:
                img = None
                try:
                    img = Image.open(image_path).convert("RGB")
                    opened_images.append(img)  # 추적 목록에 추가
                    ocr_text = _safe_ocr(img)
                    if ocr_text:
                        text_with_ocr += f"\n{ocr_text}\n"
                        debug(f"✅ OCR 완료: {image_path}")
                except Exception as e:
                    # OOM 에러인지 확인 (ocr_processing의 _is_oom_error 사용)
                    from src.document_processing.ocr_processing import _is_oom_error
                    if _is_oom_error(e):
                        # OOM 에러는 재발생시켜 상위 재시도 메커니즘이 작동하도록 함
                        warning(f"⚠️ OCR OOM 에러 발생 {image_path}: {str(e)}")
                        raise
                    else:
                        # 일반 에러는 로그만 출력하고 계속 진행
                        warning(f"⚠️ OCR 실패 {image_path}: {str(e)}")
                finally:
                    # 이미지 파일 명시적으로 닫기 (삭제 시 파일 사용 중 오류 방지)
                    if img is not None:
                        try:
                            img.close()
                        except Exception:
                            pass
        finally:
            # 모든 이미지가 닫혔는지 확인
            for img in opened_images:
                try:
                    if hasattr(img, 'fp') and img.fp is not None:
                        img.close()
                except Exception:
                    pass
            debug(f"✅ OCR 처리 완료, 모든 이미지 파일 닫힘")
        
        # # 마크다운 파일로 저장
        # if text_with_ocr:
        #     save_markdown_result(text_with_ocr, filename, "_ocr")
            # print(f"OCR 적용 후 마크다운 길이: {len(text_with_ocr)}")
        
        return text_with_ocr
    
    def _process_regular_document(self, file_path: str) -> str:
        """일반 문서 처리 (docling 사용)"""
        try:
            processing_result = process_document(file_path)
            
            # 딕셔너리인지 확인하고 처리
            if isinstance(processing_result, dict):
                embedded_markdown = processing_result["embedded_markdown"]
            else:
                embedded_markdown = processing_result
            
            return embedded_markdown
            
        except Exception as processing_error:
            # PDF 처리 실패 시 PDF 재작성 시도 (라이선스 안전한 체인)
            if file_path.lower().endswith(".pdf"):
                warning(f"⚠️ Initial PDF extraction failed: {str(processing_error)}")

                import os
                from typing import Optional

                # 변환된 PDF를 저장할 별도 폴더
                converted_pdf_dir = "./converted_pdfs"
                os.makedirs(converted_pdf_dir, exist_ok=True)

                # 변환된 PDF 파일 경로
                original_filename = os.path.basename(file_path)
                converted_filename = os.path.splitext(original_filename)[0] + "_converted.pdf"
                converted_pdf_path = os.path.join(converted_pdf_dir, converted_filename)
                self.saved_files.append(converted_pdf_path)  # 저장용 파일로 분류

                def process_and_return(_path: str):
                    processing_result = process_document(_path)
                    if isinstance(processing_result, dict):
                        return processing_result.get("embedded_markdown", processing_result)
                    return processing_result

                # --- 방법 1: pypdf (복사-재작성; 가장 단순하고 빠름) ---
                try:
                    from pypdf import PdfReader, PdfWriter
                    debug(f"🔧 Attempting PDF repair using pypdf for {file_path}...")

                    reader = PdfReader(file_path, strict=False)
                    writer = PdfWriter()

                    for page in reader.pages:
                        writer.add_page(page)

                    # 메타데이터가 문제를 일으킬 수 있으므로 복사 시 예외 처리
                    try:
                        if reader.metadata:
                            writer.add_metadata(reader.metadata)
                    except Exception:
                        pass

                    with open(converted_pdf_path, "wb") as output_file:
                        writer.write(output_file)

                    info(f"✅ pypdf repaired PDF saved to {converted_pdf_path}")
                    return process_and_return(converted_pdf_path)

                except Exception as pypdf_error:
                    warning(f"⚠️ pypdf repair failed: {str(pypdf_error)}")

                    # --- 방법 2: pikepdf (기본 옵션) ---
                    try:
                        import pikepdf
                        debug(f"🔧 Attempting PDF repair using pikepdf (basic) for {file_path}...")

                        with pikepdf.open(file_path) as pdf:
                            pdf.save(
                                converted_pdf_path,
                                compress_streams=True,
                                normalize_content=True
                            )

                        info(f"✅ pikepdf (basic) repaired PDF saved to {converted_pdf_path}")
                        return process_and_return(converted_pdf_path)

                    except Exception as pikepdf_basic_error:
                        warning(f"⚠️ pikepdf (basic) repair failed: {str(pikepdf_basic_error)}")

                        # --- 방법 3: pikepdf (고급 옵션) ---
                        try:
                            import pikepdf
                            debug(f"🔧 Attempting PDF repair using pikepdf (advanced) for {file_path}...")

                            with pikepdf.open(file_path) as pdf:
                                # 손상된 object stream을 비활성화하여 재작성 시도
                                save_kwargs = {
                                    "compress_streams": True,
                                    "normalize_content": True,
                                    "object_stream_mode": pikepdf.ObjectStreamMode.disable
                                }
                                # preserve_pdfa는 지원되는 버전에서만 사용
                                try:
                                    save_kwargs["preserve_pdfa"] = True
                                except (TypeError, AttributeError):
                                    pass
                                
                                pdf.save(converted_pdf_path, **save_kwargs)

                            info(f"✅ pikepdf (advanced) repaired PDF saved to {converted_pdf_path}")
                            return process_and_return(converted_pdf_path)

                        except Exception as pikepdf_advanced_error:
                            error(f"❌ pikepdf (advanced) repair failed: {str(pikepdf_advanced_error)}")
                            error(f"❌ All PDF repair methods failed. Last error: {str(pikepdf_advanced_error)}")
                            # 원래의 processing_error를 다시 던져 상위 레이어의 에러 핸들링을 유지
                            raise processing_error
            else:
                # PDF가 아니면 원래 예외
                raise processing_error

    
    def _post_process_text(self, markdown_text: str, genre: str, filename: str) -> str:
        """텍스트 후처리 (OCR 적용, 긴 문단 제거, 섹션 제거)"""
        # OCR 적용
        markdown_with_ocr = inject_image_ocr(markdown_text)
        info("=== OCR 처리 완료 ===")
        info(f"📊 OCR 적용 후 마크다운 길이: {len(markdown_with_ocr)}")
        
        # OCR 마크다운 저장
        save_markdown_result(markdown_with_ocr, filename, "_with_ocr", "# OCR이 적용된 마크다운 결과\n\n")
        
        # 긴 문단 제거
        format_type = "remember" if genre == "remember" else "default"
        
        if genre == "remember":
            # Remember 형식의 경우 더 엄격한 기준 적용
            debug("📋 Remember 형식의 경우 더 엄격한 기준 적용")
            markdown_cv_only = remove_long_paragraphs_by_sentences_ocr(
                markdown_with_ocr,
                sentence_count_threshold=20,
                avg_length_threshold=2000,
                format_type=format_type
            )
        
        else:
            # 기타 형식의 경우
            markdown_cv_only = remove_long_paragraphs_by_sentences_ocr(
                markdown_with_ocr,
                sentence_count_threshold=5,
                avg_length_threshold=80,
                format_type=format_type
            )
        
        # 모든 genre에서 논문 섹션 추출 시도
        sections_journal_result = None
        try:
            # genre에 따라 적절한 함수 선택
            if genre == "normal":
                # normal genre는 영어/국제 저널용 함수 사용
                sections_journal_result = extract_sections_journal_result(markdown_cv_only)
                result_type = "영어/국제 저널"
            else:
                # remember, 기타 genre는 한국어/다른 장르용 함수 사용
                sections_journal_result = extract_sections_korean_result(markdown_cv_only)
                result_type = "한국어/다른 장르"
            
            if sections_journal_result["sections_journal_result"]:
                save_markdown_result(
                    sections_journal_result["sections_journal_result"], 
                    filename, 
                    "_sections_journal_result",
                    f"# 추출된 논문 섹션들 ({result_type})\n\n"
                )
                info(f"📄 {result_type} 논문 섹션 추출 완료: {sections_journal_result['removed_count']}개 라인")
            else:
                debug(f"📄 {result_type} 논문 섹션이 없어 논문 정보 추출 생략")
        except Exception as e:
            warning(f"⚠️ 논문 섹션 추출 중 오류 발생: {str(e)}")
            sections_journal_result = None
        
        # 논문 섹션 제거 (추출 성공 여부와 관계없이 항상 실행)
        try:
            if genre == "normal":
                # normal genre는 영어/국제 저널용 함수 사용
                section_removal_result = remove_sections_journal(markdown_cv_only)
                markdown_cv_only = section_removal_result["filtered_text"]
                debug(f"🗑️ normal genre 논문 섹션 제거 후 길이: {len(markdown_cv_only)}")
            else:
                # remember, 기타 genre는 한국어/다른 장르용 함수 사용
                section_removal_result = remove_sections_korean(markdown_cv_only)
                markdown_cv_only = section_removal_result["filtered_text"]
                debug(f"🗑️ {genre} genre 논문 섹션 제거 후 길이: {len(markdown_cv_only)}")
        except Exception as e:
            warning(f"⚠️ 논문 섹션 제거 중 오류 발생: {str(e)}")
            # 오류 발생 시 원본 텍스트 사용
            pass
        
        # 자기소개서 섹션 삭제 적용 (remember, 기타 genre만)
        try:
            if genre != "normal":
                # remember, 기타 genre는 한국어/다른 장르용 함수 사용
                section_removal_result = remove_sections_korean(markdown_cv_only)
                markdown_cv_only = section_removal_result["filtered_text"]
                debug(f"🗑️ {genre} genre 자기소개서 섹션 제거 후 길이: {len(markdown_cv_only)}")
                info(f"📝 {genre} genre: 자기소개서 섹션 삭제 완료")
            else:
                debug("📝 normal genre: 긴 문단 제거 처리 생략, 모든 내용 보존")
        except Exception as e:
            warning(f"⚠️ 자기소개서 섹션 제거 중 오류 발생: {str(e)}")
            # 오류 발생 시 원본 텍스트 사용
            pass

        
        # 최종 결과 저장
        save_markdown_result(markdown_cv_only, filename, "_cv_only_by_sentences")
        debug("✅ 긴 문단 제거 결과 저장 완료")
        info(f"📊 문장 기준 긴 문단 제거 후 마크다운 길이: {len(markdown_cv_only)}")
        
        return markdown_cv_only, sections_journal_result
    
    def _cleanup_temp_files(self) -> None:
        """임시 파일들 정리 (OCR 프로세스 완료 후 호출됨)"""
        # 임시 파일들 삭제
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except (OSError, FileNotFoundError):
                pass
        self.temp_files.clear()
        
        # 저장된 파일들도 정리
        for saved_file in self.saved_files:
            try:
                if os.path.exists(saved_file):
                    os.unlink(saved_file)
            except (OSError, FileNotFoundError):
                pass
        self.saved_files.clear()
        
        # 임시 디렉토리들 삭제 (이미지 파일 포함)
        for temp_dir in self.temp_dirs:
            if not os.path.exists(temp_dir):
                debug(f"⚠️ [Cleanup] 디렉토리가 이미 없음: {temp_dir}")
                continue
                
            # 삭제 재시도 로직 (파일이 사용 중일 수 있음)
            max_retries = 3
            retry_delay = 0.5  # 0.5초 대기
            deleted = False
            
            for attempt in range(max_retries):
                try:
                    shutil.rmtree(temp_dir)
                    debug(f"✅ 임시 디렉토리 삭제됨: {temp_dir}")
                    deleted = True
                    break
                except (OSError, FileNotFoundError, PermissionError) as e:
                    if attempt < max_retries - 1:
                        debug(f"⚠️ 디렉토리 삭제 재시도 ({attempt + 1}/{max_retries}): {temp_dir}")
                        time.sleep(retry_delay)
                    else:
                        warning(f"❌ 디렉토리 삭제 실패 (재시도 {max_retries}회 후): {temp_dir} - {str(e)}")
                except Exception as e:
                    # 예상치 못한 예외도 로깅
                    error(f"❌ 디렉토리 삭제 중 예상치 못한 오류: {temp_dir} - {type(e).__name__}: {str(e)}")
                    break
            
            # 재시도 후에도 실패한 경우, 개별 파일 삭제 시도
            if not deleted and os.path.exists(temp_dir):
                try:
                    debug(f"⚠️ 개별 파일 삭제 시도: {temp_dir}")
                    for root, dirs, files in os.walk(temp_dir, topdown=False):
                        for name in files:
                            file_path = os.path.join(root, name)
                            try:
                                os.unlink(file_path)
                            except Exception as e:
                                debug(f"  ⚠️ 파일 삭제 실패: {file_path} - {str(e)}")
                        for name in dirs:
                            dir_path = os.path.join(root, name)
                            try:
                                os.rmdir(dir_path)
                            except Exception:
                                pass
                    # 최종적으로 디렉토리 삭제 시도
                    try:
                        os.rmdir(temp_dir)
                        debug(f"✅ 디렉토리 삭제 완료 (개별 파일 삭제 후): {temp_dir}")
                    except Exception:
                        pass
                except Exception as e:
                    warning(f"❌ 개별 파일 삭제도 실패: {temp_dir} - {str(e)}")
        
        # temp_dirs에 추가되지 않은 고아 디렉토리 정리 (clear 전에 확인)
        current_dirs = set(self.temp_dirs)
        self.temp_dirs.clear()
        
        # /app/images 폴더 정리
        images_base_dir = "/app/images"
        if os.path.exists(images_base_dir):
            try:
                # 1. 직접 저장된 이전 버전 파일들 삭제 (page_*.png)
                for item in os.listdir(images_base_dir):
                    item_path = os.path.join(images_base_dir, item)
                    if os.path.isfile(item_path) and item.startswith("page_") and item.endswith(".png"):
                        try:
                            os.unlink(item_path)
                            debug(f"✅ 이전 버전 이미지 파일 삭제됨: {item_path}")
                        except (OSError, FileNotFoundError) as e:
                            warning(f"❌ 파일 삭제 실패 {item_path}: {str(e)}")
                
                # 2. temp_dirs에 추가되지 않은 고아 디렉토리들도 정리
                # (예외 발생 등으로 temp_dirs에 추가되지 않은 경우)
                for item in os.listdir(images_base_dir):
                    item_path = os.path.join(images_base_dir, item)
                    if os.path.isdir(item_path) and item_path not in current_dirs:
                        # 고아 디렉토리 발견 - 삭제 시도
                        try:
                            # 최근 수정 시간 확인 (60초 이상 된 디렉토리만 삭제)
                            # (현재 처리 중인 디렉토리일 수 있으므로 조심스럽게)
                            if os.path.exists(item_path):
                                dir_mtime = os.path.getmtime(item_path)
                                if time.time() - dir_mtime > 60:  # 1분 이상
                                    shutil.rmtree(item_path)
                                    debug(f"✅ 고아 디렉토리 삭제됨 (60초 이상 경과): {item_path}")
                        except Exception as e:
                            warning(f"⚠️ 고아 디렉토리 삭제 실패 {item_path}: {str(e)}")
            except (OSError, PermissionError) as e:
                error(f"❌ 이미지 디렉토리 스캔 실패: {str(e)}")


def preprocess_document(file: UploadFile) -> Tuple[str, str, Optional[Dict], Optional[Dict]]:
    """
    문서 전처리 함수 (편의 함수)
    
    Args:
        file: 업로드된 파일
        
    Returns:
        Tuple[str, str, Optional[Dict], Optional[Dict]]: (processed_markdown, genre, remember_result, sections_journal_result)
    """
    preprocessor = DocumentPreprocessor()
    return preprocessor.preprocess_document(file)