[app]

title = 存款管理
package.name = depositmanager
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,db,json
version = 1.0.0
requirements = python3,kivy==2.3.0,chardet
orientation = portrait
fullscreen = 0
# Android 权限（逗号后不要有空格也可以，但建议空格）
android.permissions = WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.api = 30
android.minapi = 21
android.ndk = 23c
android.archs = arm64-v8a
android.debug = True
[buildozer]
log_level = 2
