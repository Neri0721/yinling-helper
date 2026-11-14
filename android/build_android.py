# -*- coding: utf-8 -*-
"""生成 Android WebView 壳工程（Android Studio 打开即可编译 APK）"""

import os

ROOT = r"C:\Users\风又音理233\Desktop\银龄核查助手\android"

FILES = {}

FILES["settings.gradle"] = '''pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "银龄核查助手"
include ':app'
'''

FILES["build.gradle"] = '''plugins {
    id 'com.android.application' version '8.1.4' apply false
}
'''

FILES["gradle.properties"] = '''org.gradle.jvmargs=-Xmx2048m
android.useAndroidX=true
android.nonTransitiveRClass=true
'''

FILES["app/build.gradle"] = '''plugins {
    id 'com.android.application'
}

android {
    namespace 'com.yinling.checker'
    compileSdk 34

    defaultConfig {
        applicationId "com.yinling.checker"
        minSdk 23
        targetSdk 34
        versionCode 1
        versionName "1.0"
    }

    buildTypes {
        release {
            minifyEnabled false
        }
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
}

dependencies {
    implementation 'androidx.appcompat:appcompat:1.6.1'
}
'''

FILES["app/src/main/AndroidManifest.xml"] = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.CAMERA" />

    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:usesCleartextTraffic="true"
        android:theme="@android:style/Theme.Material.Light.NoActionBar"
        android:icon="@android:drawable/sym_def_app_icon">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
'''

FILES["app/src/main/res/values/strings.xml"] = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">银龄核查</string>
</resources>
'''

FILES["app/src/main/res/layout/activity_main.xml"] = '''<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">

    <WebView
        android:id="@+id/web"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />
</FrameLayout>
'''

MAIN = '''package com.yinling.checker;

import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.KeyEvent;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView web;
    private ValueCallback<Uri[]> filePathCallback;
    private final static int FILE_CHOOSER = 1001;
    private SharedPreferences sp;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        sp = getSharedPreferences("yinling", MODE_PRIVATE);
        web = findViewById(R.id.web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setSupportZoom(false);
        s.setAllowFileAccess(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, int code, String desc, String url) {
                askAddress("页面打不开（" + desc + "），请检查电脑上的服务是否开着，并确认地址正确。");
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb,
                                             FileChooserParams params) {
                filePathCallback = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("image/*");
                try {
                    startActivityForResult(Intent.createChooser(i, "选择图片"), FILE_CHOOSER);
                } catch (Exception e) {
                    filePathCallback = null;
                    return false;
                }
                return true;
            }
        });

        String saved = sp.getString("server", "http://10.218.45.21:8765");
        web.loadUrl(saved + "/m");
    }

    private void askAddress(String tip) {
        final EditText et = new EditText(this);
        et.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        et.setText(sp.getString("server", "http://10.218.45.21:8765"));
        new AlertDialog.Builder(this)
                .setTitle("设置服务器地址")
                .setMessage(tip)
                .setView(et)
                .setPositiveButton("保存并打开", (d, w) -> {
                    String v = et.getText().toString().trim();
                    if (v.endsWith("/")) v = v.substring(0, v.length() - 1);
                    sp.edit().putString("server", v).apply();
                    web.loadUrl(v + "/m");
                })
                .setNegativeButton("取消", null)
                .show();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER && filePathCallback != null) {
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                results = new Uri[]{data.getData()};
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && web.canGoBack()) {
            web.goBack();
            return true;
        }
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            new AlertDialog.Builder(this)
                    .setTitle("设置")
                    .setItems(new String[]{"修改服务器地址"}, (d, w) -> askAddress(""))
                    .setNegativeButton("取消", null)
                    .show();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}
'''

FILES["app/src/main/java/com/yinling/checker/MainActivity.java"] = MAIN

README = '''# 安卓打包说明

这是一个 WebView 壳工程：界面就是网页，好处是以后改网页不用重新发版。

## 一、准备

1. 装 Android Studio（约 1.2 GB）：https://developer.android.com/studio
2. 首次启动按提示装 SDK（Andrid 14 / API 34 即可）

## 二、打开并编译

1. Android Studio → Open → 选择本目录 `android`
2. 等右下角 Gradle Sync 完成（首次会下载依赖，几分钟）
3. 菜单 Build → Build Bundle(s) / APK(s) → Build APK(s)
4. 完成后点通知里的 "locate"，APK 在：
   `app/build/outputs/apk/debug/app-debug.apk`

## 三、装到手机

方式 A（数据线）：手机开 USB 调试，Android Studio 直接 Run ▶

方式 B（发文件）：把 app-debug.apk 发到手机（微信/QQ/网盘），
手机上点开、允许"安装未知应用"即可。

## 四、第一次打开

App 会加载 `http://10.218.45.21:8765/m`。
如果这个地址不对（电脑 IP 变了），
**按手机返回键**会弹出"修改服务器地址"，填新的地址即可。

查当前地址：电脑上运行 `curl http://127.0.0.1:8765/api/stats`

## 五、注意事项

- 手机和电脑要在同一个 Wi-Fi 下
- 电脑上的 `server.py` 必须开着
- 电脑防火墙要放行 8765（管理员 PowerShell）：
  `New-NetFirewallRule -DisplayName "yinling-8765" -Direction Inbound -LocalPort 8765 -Protocol TCP -Action Allow -Profile Any`
- 现在用的是 http，`usesCleartextTraffic` 已打开；正式上线应换 https
- 拍照按钮走的是网页的文件选择，安卓会弹出"相机 / 文件"选择框

## 六、如果要装到别人手机上

先把服务部署到公网（华为云 ECS 或内网穿透），
再把 `MainActivity.java` 里的默认地址改成公网地址，重新打包。
'''

FILES["README.md"] = README


def main():
    for rel, content in FILES.items():
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print("  %-58s %5d B" % (rel, len(content.encode("utf-8"))))
    print("共 %d 个文件 -> %s" % (len(FILES), ROOT))


if __name__ == "__main__":
    main()
