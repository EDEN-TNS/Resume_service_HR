# Dockerfile.ko
FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app

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

# 런타임에 필요한 것만 이미지에 포함 (비밀/캐시 제외)
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY swagger_ui /app/swagger_ui

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "src.api.main"]
