name: Build APK (native)

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          sudo apt update
          sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config automake libffi-dev build-essential wget curl
          pip install --upgrade pip
          pip install cython buildozer

      - name: Build APK
        run: |
          export BUILDOZER_RUN_AS_ROOT=1
          buildozer android debug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: my-apk
          path: ./bin/*.apk
