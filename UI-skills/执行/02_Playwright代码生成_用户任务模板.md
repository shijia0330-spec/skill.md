# 用户任务模板 — 填好 `{analysis_summary}` 再生成代码

占位符：**`{analysis_summary}`**（拼法见 **`03_分析摘要构建说明.md`**）。

---

## 1. 干啥用

把「验收意图 + 可选控件表 + Python 侧底线」一次性喂给模型，让它吐出 **`test_*.py`**。  
默认 **不要**逼模型写 TypeScript；也不要把 MidScene 当主命令。

---

## 2. 模板正文（可直接复制改）

```
你是有经验的测试开发，按下面摘要写 pytest-playwright（Python）自动化。

{analysis_summary}

## 必须遵守

1. Python 3；pytest；`from playwright.sync_api import Page, expect`。
2. 输出 ```python 代码块；代码块外不要解释。
3. 用 pytest-playwright 的 `page` fixture，不要自己 new browser 不关。
4. 点击输入优先：testid → role+name → label/placeholder → 带父级的 locator；视觉兜底只在摘要明确要求时用。
5. 断言用 expect(locator)，少用裸 assert 拼 inner_text。
6. 需要等服务端回包时用 wait_for_response；不要随便 sleep。
7. 账号从 os.environ 读，示例给出键名，不要写真实密码。

## 建议

- 每个 test 顶上加 docstring，带 TC-UI 编号。
- 列表项若用 first，说明为何唯一。

## 不要这样干

- 全文匹配「提交」且不加父级 —— 容易点错。
- 导航没完就断言 URL。

## 写完自检

能 `python3 -m py_compile`；缺摘要信息就 pytest.skip 说明原因，别瞎编选择器。
```

---

## 3. 数据从哪流过来

分析 / 用户输入 → 拼摘要 → 塞本模板 → 模型 → 人工扫一眼 → 进 CI。

---

## 4. 维护

Playwright 或插件升级时，只改「必须遵守」那几条，别到处复制粘贴。
