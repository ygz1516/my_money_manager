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

      - name: Install Flutter SDK
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.41.7'
          channel: 'stable'
          cache: true

      - name: Install Python dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt

      - name: Build APK
        run: flet build apk --module-name deposit_app_flet --requirements requirements.txt

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: deposit-app
          path: build/apk/*.apk
