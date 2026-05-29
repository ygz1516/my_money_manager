name: Build Flet APK

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Flutter dependencies (accept licenses)
        run: |
          sudo apt-get update
          sudo apt-get install -y curl git unzip xz-utils zip libglu1-mesa
          git clone https://github.com/flutter/flutter.git --depth 1 -b stable
          echo "$GITHUB_WORKSPACE/flutter/bin" >> $GITHUB_PATH
        shell: bash

      - name: Accept Android licenses
        run: |
          yes | flutter doctor --android-licenses || true
        shell: bash

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install --upgrade flet

      - name: Prepare entry point
        run: |
          cp main.py deposit_app_flet.py

      - name: Build APK with Flet
        run: |
          flet build apk --verbose

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: deposit-app-apk
          path: build/apk/*.apk
