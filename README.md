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

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y curl git unzip xz-utils zip libglu1-mesa

      - name: Install Flutter (for license acceptance)
        run: |
          git clone https://github.com/flutter/flutter.git --depth 1 -b stable
          echo "$GITHUB_WORKSPACE/flutter/bin" >> $GITHUB_PATH

      - name: Accept Android licenses
        run: |
          yes | flutter doctor --android-licenses || true

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install --upgrade flet

      - name: Build APK (non-interactive)
        env:
          FLET_YES: 1
          FLUTTER_ROOT: ${{ github.workspace }}/flutter
        run: |
          export PATH="$FLUTTER_ROOT/bin:$PATH"
          echo "y" | flet build apk main.py --verbose

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: deposit-app-apk
          path: build/apk/*.apk
