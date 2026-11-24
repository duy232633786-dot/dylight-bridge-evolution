# DYLIGHT Lab — bản web công khai (scripts/serve_public.py).
# Chạy được trên Hugging Face Spaces (Docker), Render, Railway, Fly.io...
#   docker build -t dylight-lab .
#   docker run --rm -p 7860:7860 dylight-lab   → http://localhost:7860/lab.html
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=7860 \
    DYLIGHT_TRUST_PROXY=1 \
    DYLIGHT_ARTIFACTS_DIR=/tmp/dylight-public

# Người dùng thường (uid 1000), không chạy bằng root.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --chown=root:root . /app
RUN pip install -e . && rm -rf /root/.cache

# Mã nguồn thuộc root và chỉ đọc với tiến trình web; chỉ /tmp ghi được.
USER app
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.environ.get('PORT','7860'),timeout=4)"

CMD ["python", "scripts/serve_public.py"]
