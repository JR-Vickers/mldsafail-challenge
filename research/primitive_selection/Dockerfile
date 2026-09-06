FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db

ARG RESEARCH_GIT_REVISION=unknown
ARG RESEARCH_GIT_DIRTY=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    PRIMITIVE_STUDY_GIT_REVISION=$RESEARCH_GIT_REVISION \
    PRIMITIVE_STUDY_GIT_DIRTY=$RESEARCH_GIT_DIRTY

RUN apt-get update \
    && apt-get install --no-install-recommends --yes libgmp10 libmpfr6 \
    && rm -rf /var/lib/apt/lists/*

COPY research/primitive_selection/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt

WORKDIR /study
COPY research /study/research

ENTRYPOINT ["python", "-m", "research.primitive_selection"]
