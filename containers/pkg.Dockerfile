FROM python:3.10-slim

WORKDIR /root
ENV VENV /opt/venv
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONPATH /root

# If GPUs are involved
ENV NVIDIA_VISIBLE_DEVICES=all
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib64

# If debian-based parent image
RUN apt-get update && apt-get install -y build-essential

ENV VENV /opt/venv

RUN python3 -m venv ${VENV}
ENV PATH="${VENV}/bin:$PATH"

COPY . /root

# Local development
RUN pip install --upgrade pip && \
    pip install -e .
# Install from PyPI
# RUN pip install flytezen==0.1.0

ARG tag
ENV FLYTE_INTERNAL_IMAGE $tag
