# BLACKBOX - one application container (scikit-learn + XGBoost hybrid gate).
#
# Build and verify ON the target machine (LinuxONE / s390x), not on an x86 laptop:
#     # x86/amd64: wheels exist for every dependency
#     docker build -t blackbox .
#     # s390x: scikit-learn and xgboost have no wheels -> compile inside the image
#     docker build --build-arg BASE_IMAGE=s390x/python:3.11-bookworm \
#                  --build-arg INSTALL_BUILD_TOOLS=1 -t blackbox .
#     docker run -d --name blackbox -p 8000:8000 blackbox
#     curl -s http://127.0.0.1:8000/health      # architecture must read s390x there
#
# If a dependency still fails on s390x, run with the documented numpy fallback:
#     docker run -e BLACKBOX_MODEL_BACKEND=numpy ...
#   (the certificate then reports the numpy models; do not describe them as
#    scikit-learn).  BLACKBOX_HYBRID_RISK=off disables the XGBoost members
#   (auto/on/off; auto = activate iff xgboost imports).
ARG BASE_IMAGE=python:3.11-slim-bookworm
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# cmake/g++/gfortran only for source builds (s390x: scipy, scikit-learn, xgboost).
ARG INSTALL_BUILD_TOOLS=0
RUN if [ "$INSTALL_BUILD_TOOLS" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
        cmake g++ make gfortran libopenblas-dev pkg-config \
      && rm -rf /var/lib/apt/lists/*; \
    fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
