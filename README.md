name: Build Android APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        arch: [arm64-v8a, armeabi-v7a]

    steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install system dependencies
      run: |
        sudo apt update
        sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev

    - name: Install buildozer and dependencies
      run: |
        pip install --upgrade pip
        pip install buildozer cython
        # 验证安装
        buildozer --version

    - name: Build APK with buildozer
      run: |
        # 如果需要针对特定架构，可以设置环境变量
        export ARCH=${{ matrix.arch }}
        buildozer android debug

    - name: Upload APK
      uses: actions/upload-artifact@v4
      with:
        name: my-apk-${{ matrix.arch }}
        path: ./bin/*.apk
