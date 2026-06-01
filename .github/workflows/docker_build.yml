FROM python:3.11-slim-bullseye

# 避免交互式操作
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 更新源并安装依赖（直接安装 openjdk-17-jdk，无需 PPA）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    zip \
    unzip \
    openjdk-17-jdk-headless \
    autoconf \
    libtool \
    pkg-config \
    automake \
    libffi-dev \
    build-essential \
    wget \
    curl \
    locales \
    && rm -rf /var/lib/apt/lists/*

# 设置语言环境
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# 安装 Buildozer 和 Cython
RUN pip install --no-cache-dir cython buildozer

WORKDIR /app
