FROM python:3.10-slim

WORKDIR /root
ENV VENV /opt/venv
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONPATH /root

ENV NVIDIA_VISIBLE_DEVICES=all
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib64

RUN apt-get update && apt-get install -y build-essential

ENV VENV /opt/venv

RUN python3 -m venv ${VENV}
ENV PATH="${VENV}/bin:$PATH"

COPY . /root

RUN pip install --upgrade pip && \
    pip install .

ARG tag
ENV FLYTE_INTERNAL_IMAGE $tag
