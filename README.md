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
          pip install flet matplotlib pandas openpyxl chardet

      - name: Build APK with legacy packaging
        run: |
          flet build apk --module-name deposit_app_flet
          # 在生成的 Android 工程中强制启用 legacy packaging
          ANDROID_PATH="build/apk/android/app/build.gradle"
          if [ -f "$ANDROID_PATH" ]; then
            sed -i '/android {/a\    packagingOptions {\n        jniLibs {\n            useLegacyPackaging true\n        }\n    }' "$ANDROID_PATH"
            echo "Patched build.gradle for Google Play compatibility"
          fi
          # 重新构建（确保生效）
          cd build/apk
          flutter build apk --release

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: deposit-app
          path: build/apk/*.apk
