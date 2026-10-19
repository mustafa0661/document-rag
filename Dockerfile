# DENEYSEL — Bu Dockerfile geliştirme sırasında derlenip çalıştırılarak DOĞRULANMADI
# (geliştirme ortamında Docker yoktu). Resmî ve doğrulanmış çalıştırma yöntemi
# README'deki yerel Windows kurulumudur.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    EASYOCR_MODULE_PATH=/models/easyocr

# Docling/OpenCV'nin ihtiyaç duyduğu sistem kütüphaneleri
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU sürümü torch ve torchvision önce kurulur: PyPI'daki Linux paketleri
# CUDA kütüphanelerini (~5 GB) çeker. GPU gerekiyorsa bu satır değiştirilmelidir.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY streamlit_app.py .
COPY .streamlit ./.streamlit

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
