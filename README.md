name: Build Flet APK

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install flet matplotlib pandas openpyxl chardet

      - name: Build APK
        run: flet build apk --module-name deposit_app_flet

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: deposit-app
          path: build/apk/*.apk
