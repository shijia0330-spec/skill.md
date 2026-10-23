---
name: mobile-self-heal
description: Triages failing Appium/pytest mobile tests using logs, screenshots, and page structure; updates waits/locators or files product issues. Use when mobile automation fails.
---

# 移动端脚本挂了 — 怎么收敛

Appium / 真机流水线跑红时，先看 **Appium 日志、截图、当前页结构**，再决定改定位、改等待、改环境，还是报产品缺陷。默认假定修的是 **Python + pytest** 测试代码。

---

## 1. 常见几类原因

| 现象 | 多半是啥 | 常见处理 |
|------|----------|----------|
| 找不到元素 | 控件属性变了、在 WebView 里却还在原生 context | 更新定位；检查是否需 `switch_to.context` |
| Session / Driver 起不来 | 端口占用、capabilities 错、设备未连上 | 核对 `udid`、App 路径、系统版本与 driver 匹配 |
| Stale element | 列表刷新后句柄失效 | 重新查找元素；避免缓存过久引用 |
| 超时 | 动画、接口慢、弱网 | 等对的应用就绪再操作；别只会全局加大超时 |
| 权限 / 系统弹窗挡操作 | 未处理允许/拒绝 | 用固定步骤处理该类弹窗 |
| 安装失败 | 签名、版本降级、存储满 | 看 adb / idevice 输出，换包或清数据 |

---

## 2. 自愈步骤（带代码）

### Step 1：捕获失败信息

codegen 脚本已内置 `pytest_runtest_makereport`：失败时自动保存  
`output/appium_artifacts/<用例>_fail.png` 与 `_source.xml`。

手动补充（旧脚本）：

### Step 2：定位器失效修复

**可执行工具**（优先）：

```bash
# 失败产物 → 候选定位器 JSON
python3 mobile-skills/执行/scripts/locator_healer.py \
  -i output/appium_artifacts/test_xxx_source.xml \
  --by css --locator 'input[name="username"]'

# 或先 scan 再人工挑
python3 mobile-skills/执行/scripts/scan_page_source.py -i output/appium_artifacts/xxx_source.xml
```

**运行时自愈**：codegen 生成脚本的 `_find()` 默认 `MOBILE_SELF_HEAL=1`，按 L1→L2→L3（page_source 推断）重试。关闭：`MOBILE_SELF_HEAL=0`。

核心实现：`codegen/mobile_lib/locator_healer.py`（与 Web 端 `UI-skills/执行/scripts/locator_healer.py` 对齐思路）。

手动兜底示例：

```python
def heal_locator(driver, old_locator):
    """自动查找新定位器"""
    # 获取当前页面所有可交互元素
    page_source = driver.page_source
    
    # 方案 A：按文本内容反查
    if old_locator.get("text"):
        new_id = find_element_by_text(page_source, old_locator["text"])
        if new_id:
            return {"by": "id", "value": new_id}
    
    # 方案 B：按邻近元素查找
    if old_locator.get("near"):
        new_loc = find_near_element(driver, old_locator["near"])
        if new_loc:
            return new_loc
    
    # 方案 C：降级到 XPath 模糊匹配
    return {"by": "xpath", "value": f"//*[contains(@text, '{old_locator.get('hint', '')}')]"}
```

### Step 3：Context 切换修复

```python
def heal_context(driver, expected_context="WEBVIEW"):
    """自动切换到正确的 context"""
    contexts = driver.contexts
    for ctx in contexts:
        if expected_context in ctx:
            driver.switch_to.context(ctx)
            return True
    # 没找到 WebView，可能页面还没加载完
    time.sleep(2)
    contexts = driver.contexts
    for ctx in contexts:
        if expected_context in ctx:
            driver.switch_to.context(ctx)
            return True
    return False
```

---

## 3. 常见修复模式

### 定位器更新

```python
# 旧定位器（失效）
# driver.find_element(AppiumBy.ID, "com.example:id/old_btn").click()

# 修复后：先查页面找新 ID
elements = driver.find_elements(AppiumBy.XPATH, "//*[@content-desc='登录']")
if elements:
    elements[0].click()
```

### 等待策略调整

```python
# 旧：全局 sleep（不好）
# time.sleep(10)

# 修复：等元素出现再操作
WebDriverWait(driver, 15).until(
    EC.presence_of_element_located((AppiumBy.ID, "com.example:id/submit_btn"))
)
```

---

## 4. 和谁配合

确认是应用逻辑错误走 **bug-reporter**；只是定位飘了优先推动可测性属性，再改脚本。

---

## 5. 几条习惯

- 不要在同一问题上自动重试超过 3 次
- 优先改定位/等待策略，不改业务校验逻辑
- 截图和 page_source 是排查的关键证据，必须保留
- context 切换问题（Native vs WebView）是最容易被忽略的一类
