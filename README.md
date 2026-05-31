name: Build Android APK

on: push: branches: [ main ] workflow_dispatch:

jobs: build: runs-on: ubuntu-latest strategy: matrix: arch: [arm64-v8a, armeabi-v7a]

steps:
- name: Checkout
  uses: actions/checkout@v4

- name: Build with Buildozer
  uses: michaelkrukov/buildozer-action@v1
  with:
    command: buildozer android debug
    buildozer_spec_path: buildozer.spec
    workdir: .
    python_version: 3.11

- name: Upload APK
  uses: actions/upload-artifact@v4
  with:
    name: my-apk-${{ matrix.arch }}
    path: ./bin/*.apk
