# Usar Debian Bullseye que tiene libwebp6
FROM python:3.11-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libpng16-16 \
    libjpeg62-turbo \
    libtiff5 \
    libopenblas0 \
    libx11-6 \
    libsm6 \
    libxext6 \
    libwebp6 \
    file \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip

# ✅ Instalar dlib precompilado
RUN pip install --no-cache-dir \
    https://github.com/alvinregin/dlib-wheels/releases/download/v20.0.0/dlib-20.0.0-cp311-cp311-linux_x86_64.whl

# ✅ Verificar que dlib se instaló correctamente
RUN python -c "import dlib; print('dlib version:', dlib.__version__)"

# ✅ Instalar face_recognition_models
RUN pip install --no-cache-dir \
    git+https://github.com/ageitgey/face_recognition_models

# ✅ Instalar requirements
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Verificar que face_recognition funciona
RUN python -c "import face_recognition; print('face_recognition import successful')"

COPY . .

EXPOSE 5000

# Reemplaza tu CMD original por este:
CMD ["gunicorn", "-b", "0.0.0.0:5000", "--worker-class=gthread", "--workers=1", "--threads=8", "main:app"]