FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
RUN apt-get update && apt-get install --no-install-recommends --yes libgmp10=2:6.2.1+dfsg1-1.1 libmpfr6=4.2.0-1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /requirements.txt
COPY wheels /wheels
RUN if [ -z "$(ls -A /wheels)" ]; then pip download --only-binary=:all: --dest /wheels -r /requirements.txt; fi && pip install --no-index --find-links=/wheels -r /requirements.txt
COPY artifacts.py /artifacts.py
RUN python /artifacts.py > /artifacts.json
WORKDIR /worker
COPY mldsafail /worker/mldsafail
USER 65534:65534
ENTRYPOINT ["python", "-m", "mldsafail.benchmark_v050.worker"]
