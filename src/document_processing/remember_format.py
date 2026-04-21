from PIL import Image
import os
import uuid

from src.llm_extraction.resume_schema import ResumeExtraction


def process_remember(pdf, unique_id=None, **kwargs):
    """
    PDF의 모든 페이지를 이미지로 변환하는 함수
    섹션 분할 없이 전체 페이지를 이미지로 저장
    
    Args:
        pdf: PDF 객체
        unique_id: 각 요청을 구분하기 위한 고유 식별자 (없으면 UUID 생성)
    """
    all_page_images = []
    
    # 고유 식별자 생성 (없으면 UUID 사용)
    if unique_id is None:
        unique_id = str(uuid.uuid4())
    
    # 각 요청마다 고유한 디렉토리 생성
    output_dir = os.path.join("/app/images", unique_id)
    os.makedirs(output_dir, exist_ok=True)
    
    # 모든 페이지를 이미지로 변환
    for idx, page in enumerate(pdf.pages):
        page_image = page.to_image(resolution=600)
        
        # 영구 저장을 위한 파일명 생성
        image_filename = f"page_{idx+1}.png"
        image_path = os.path.join(output_dir, image_filename)
        
        # 이미지 저장
        page_image.save(image_path, format="PNG")
        all_page_images.append(image_path)
        # print(f"이미지 저장됨: {image_path}")
    
    return all_page_images

def extract_remember(pdf, unique_id=None, **kwargs):
    """
    PDF를 이미지로 변환하는 함수
    섹션 분할 없이 전체 페이지를 이미지로 저장
    
    Args:
        pdf: PDF 객체
        unique_id: 각 요청을 구분하기 위한 고유 식별자
    """
    # PDF의 모든 페이지를 이미지로 변환
    all_page_images = process_remember(pdf, unique_id=unique_id)
    
    output = ResumeExtraction().model_dump(mode="json")
    output["image_paths"] = all_page_images
    return output