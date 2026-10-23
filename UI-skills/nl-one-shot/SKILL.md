---
name: ui-nl-one-shot
description: 用户用一句话在业务系统页面上完成操作；LLM 拆步骤后 Playwright 真实执行。Use for 一句话操作页面、自然语言UI、给我新增商品、在系统上执行.
---

# 自然语言一句话 UI 执行

详见同目录说明与根目录 `nl_ui_client.py`。

## 快速执行

```bash
# 1. 启动你的业务前端 + NL 服务（默认 http://your-server:5010）
# 2. 浏览器对话页 http://your-server:5010/（若已部署 NL 服务）

# 3. 或在本包根目录由 AI 调用
cd skills-专业版V3.0
export NL_API_URL=http://your-server:5010   # 可选
python3 nl_ui_client.py "给我新增一个商品" --json
```

## AI 规则

- 用户口语描述页面操作 → 调用 `nl_ui_client.py` 或 `POST http://your-server:5010/api/nl/run`
- 先 `GET /api/health` 确认 `seckill_running`
- 返回 `steps_parsed` + `step_results` 给用户；失败展示 `error`

完整文档：`UI-skills/执行/05_自然语言一句话执行.md`
