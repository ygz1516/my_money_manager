name: Docker Build APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: patrickloeber/buildozer:latest   # 更换镜像
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Build APK
        run: |
          export BUILDOZER_RUN_AS_ROOT=1
          buildozer android debug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: my-apk
          path: ./bin/*.apk
