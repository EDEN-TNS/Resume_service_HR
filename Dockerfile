# Dockerfile.ko
FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
# Docling/EasyOCR 캐시를 이미지 내부 고정 경로로 유도
# - docker-compose-hr.yml 에서도 EasyOCR는 /root/.EasyOCR 를 사용하고 있음
ENV HOME=/root
ENV XDG_CACHE_HOME=/root/.cache

# LibreOffice + 한글 폰트 + 로케일 + 유틸
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl vim gcc g++ python3-dev libffi-dev \
      fontconfig locales ca-certificates \
      libreoffice libreoffice-writer libreoffice-l10n-ko libreoffice-help-ko \
      fonts-noto-cjk fonts-nanum fonts-unfonts-core \
  && sed -i 's/# *ko_KR.UTF-8/ko_KR.UTF-8/' /etc/locale.gen \
  && locale-gen \
  && rm -rf /var/lib/apt/lists/*

# 최소 폰트 매핑
RUN printf '%s\n' \
'<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n<fontconfig>\n'\
'  <alias><family>Calibri</family>         <prefer><family>Noto Sans CJK KR</family></prefer></alias>\n'\
'  <alias><family>Arial</family>           <prefer><family>Noto Sans CJK KR</family></prefer></alias>\n'\
'  <alias><family>Times New Roman</family> <prefer><family>Noto Serif CJK KR</family></prefer></alias>\n'\
'  <alias><family>맑은 고딕</family>         <prefer><family>Noto Sans CJK KR</family></prefer></alias>\n'\
'</fontconfig>\n' > /etc/fonts/local.conf && fc-cache -f -v

ENV LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8

# 앱 의존성 (캐시 효율 위해 먼저 복사)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt

# Docling 모델 + (Docling이 사용하는) EasyOCR 모델을 빌드 시점에 미리 다운로드하여 이미지에 포함
# - Docling: docling.utils.model_downloader.download_models()
# - EasyOCR: Docling 파이프라인으로 작은 PDF를 1회 변환해 OCR을 실제로 트리거
RUN python -c "import os; os.makedirs('/root/.cache', exist_ok=True); os.makedirs('/root/.EasyOCR', exist_ok=True); from docling.utils import model_downloader; model_downloader.download_models(); from docling.datamodel.base_models import InputFormat; from docling.datamodel.pipeline_options import PdfPipelineOptions; from docling.document_converter import DocumentConverter, PdfFormatOption; from PIL import Image, ImageDraw; from io import BytesIO; img=Image.new('RGB',(600,200),(255,255,255)); d=ImageDraw.Draw(img); d.text((20,20),'prewarm ocr ko/en',(0,0,0)); b=BytesIO(); img.save(b, format='PDF'); pdf_bytes=b.getvalue(); open('/tmp/_docling_prewarm.pdf','wb').write(pdf_bytes); p=PdfPipelineOptions(); p.do_ocr=True; p.ocr_options.lang=['ko','en']; c=DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=p)}); c.convert('/tmp/_docling_prewarm.pdf')"

# 런타임에 필요한 것만 이미지에 포함 (비밀/캐시 제외)
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY swagger_ui /app/swagger_ui

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "src.api.main"]
