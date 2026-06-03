[app]
# 应用基本信息
title = 存款管理
package.name = depositmanager
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,db,json
version = 1.0.0
requirements = python3,kivy==2.3.0,chardet
orientation = portrait
fullscreen = 0

# Android 特有配置
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 30
android.minapi = 21
android.ndk = 23c
android.archs = arm64-v8a

# 允许调试（方便查看日志）
android.debug = True

# Buildozer 日志级别
[buildozer]
log_level = 2
