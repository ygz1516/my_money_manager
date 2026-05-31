name: Build Flet APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.22.5'
          channel: 'stable'

      - name: Install flet-cli
        run: pip install flet-cli

      - name: Build APK
        env:
          FLET_AGREE_FLUTTER_LICENSE: 1   # 自动同意许可，避免交互
        run: flet build apk --verbose --output build/apk

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: my-money-manager-apk
          path: build/apk/*.apk
