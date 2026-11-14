# 安卓打包说明

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
