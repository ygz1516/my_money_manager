[app]

# (str) Title of your application
title = 存款管理

# (str) Package name
package.name = depositmanager

# (str) Package domain (needed for android/ios packaging)
package.domain = org.example

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include/ignore
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,db,json
version = 1.0.0

# (list) Application requirements
requirements = python3,kivy==2.3.0,chardet

# (str) Presplash of the application
# presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
# icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (one of landscape, portrait, or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# (int) Android API level to use
android.api = 30

# (int) Minimum API level
android.minapi = 21

# (int) Android NDK version to use
android.ndk = 23c

# (list) Android architectures to build for
android.archs = arm64-v8a

# (bool) Indicate whether the app should be debuggable or not
android.debug = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2
