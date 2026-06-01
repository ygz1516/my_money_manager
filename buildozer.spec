[app]

title = 家庭存款管理
package.name = moneymanager
package.domain = org.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,db,json

version = 0.1
requirements = python3,kivy==2.3.0,matplotlib,pandas,openpyxl,chardet,numpy

orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0
fullscreen = 0

android.accept_sdk_license = True
android.minapi = 21
android.api = 31
android.ndk = 25c
android.sdk = 33
android.ndk_api = 21

android.archs = arm64-v8a, armeabi-v7a

android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

android.allow_backup = True
android.enable_androidx = True
