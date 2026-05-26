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

      - name: Install Flutter SDK (3.41.7)
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.41.7'
          channel: 'stable'
          cache: true

      - name: Install Python dependencies
        run: |
          pip install flet matplotlib pandas openpyxl chardet

      - name: Build APK (non-interactive)
        run: flet build apk --module-name deposit_app_flet --yes

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: deposit-app
          path: build/apk/*.apk
