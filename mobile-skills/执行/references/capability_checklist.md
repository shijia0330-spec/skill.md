# 移动端执行前检查（10 项）

本包 Web 主场景用 Playwright；Appium 用于 **原生壳 / 混合 App** 包装秒杀 H5 时参考。

## 环境

- [ ] Appium Server 已启动（`curl http://127.0.0.1:4723/status`）
- [ ] 设备/模拟器已连接（`adb devices`，或 Xcode 模拟器）
- [ ] `./run_appium.sh` 能列出设备且无 `offline`

## 网络（WebView / H5 必查）

- [ ] `TEST_BASE_URL` / spec `base_url` 为 **宿主机 LAN IP**（如 `192.168.x.x:5173`）
- [ ] **勿用** `127.0.0.1` / `localhost`（手机/emulator 指向自身）
- [ ] 铺底 API `base_url` 手机同样可达（通常 `:5001`）
- [ ] 防火墙放行 5173 / 5001

## 能力

- [ ] `appPackage` / `appActivity` 或 `app` 路径正确
- [ ] `setup: test_init` 已执行或 spec 默认 session 铺底成功
- [ ] 秒杀依赖 Redis 时已启动

## 脚本

- [ ] spec 使用 `kind: appium_pytest`
- [ ] `./generate.sh` + `./run_appium.sh` 成功
- [ ] 首跑 1 条 flow 验证登录再扩套件
- [ ] 复制 `templates/.env.appium.example` → `.env.appium`

## 秒杀业务冒烟（可选 3 步）

1. 打开 App / WebView 到 `${TEST_BASE_URL}/login`  
2. 登录 customer/admin  
3. 进入 `${TEST_BASE_URL}/seckill`，确认列表渲染（不强制下单）
