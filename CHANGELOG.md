# 更新日志

CuckooTilt（基于 [GravityMon](https://github.com/mp-se/gravitymon) 二次开发）的变更记录，每条对应一轮开发分支，括号内标注涉及的项目：gravitymon（固件）、gravitymon-ui（Web 界面）、espframework（ESP 框架库）。

## feat/20260909-fixes（2026-09-11 ~ 09-12，当前分支）

固件版本：8266 `2.3.3`、ESP32-C3 `3.3.5`。

- WiFi 模式页面重构：卡片布局改为响应式导航与设备总览，固件更新、恢复默认、About 归入 Tools，恢复出厂逻辑共享，修复移动端 About 导航不可见（gravitymon、gravitymon-ui）。
- WiFi 页新增 WiFi Direct 配置，支持重力模式下直连热点推送数据到 Gateway（gravitymon、gravitymon-ui）。
- 修复 WiFi 模式下 Battery 卡片不显示的问题，恢复始终展示（gravitymon、gravitymon-ui）。
- 隐藏 WiFi 模式下的 Force config mode 开关（gravitymon、gravitymon-ui）。
- 陀螺仪检测按平台门控，驱动初始化失败每次开机重试一次，并补充单元测试（gravitymon、gravitymon-ui）。
- `/push/http-post` 页支持 Predefined formats，CuckooTilt 格式补齐字段并设为固件内置默认格式（gravitymon、gravitymon-ui）。
- 新增 8.5dBm 低功耗变体：固件新增变体环境并经 `CFG_VARIANT` 与独立 OTA 目录分流，打包产物写入 `bin/` 固定路径（8.5dBm 固件名带变体后缀），Justfile 一键打包双变体并强制同步 espframework 源码（gravitymon）。
- OTA 地址抽为编译期宏 `CFG_OTAURL`，可按固件变体覆盖（espframework）。
- WiFi 发射功率支持 `ESPFWK_WIFI_TX_POWER_8_5` 定义，启用 8.5dBm 档位（espframework）。
- 打包工具链：PlatformIO 升级至 6.2.0（gravitymon）。
