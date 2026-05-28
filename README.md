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

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install flet

      - name: Build APK with Flet
        run: |
          flet build apk --verbose

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: deposit-app-apk
          path: build/apk/*.apk
