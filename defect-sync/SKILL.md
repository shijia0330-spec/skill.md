---
name: defect-sync
description: 缺陷同步引擎 — 将 Markdown 缺陷草稿推送到禅道、云效或自研平台，支持指纹去重、dry-run。
---

# 缺陷同步引擎

把 `output/bugs/` 下的缺陷草稿**推送到外部工单系统**，连接测试失败 → 禅道/云效/自研平台的最后一环。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| Markdown 草稿 → 禅道 / 云效 / 自研 Webhook | 写缺陷内容（走 bug-reporter） |
| 指纹去重，同一问题只建一次单 | AI 根因分析（走 defect-analysis） |
| dry-run 预览映射 | 状态双向回写（第一版不做） |
| **同批 + 历史指纹去重**（dry-run 也生效） | 在 Skill 里硬编码密钥 |
| **自动合并 failure_analysis.json** 到推送 payload | |

---

## 架构位置

```
pytest 失败 → defect_drafts.py → output/bugs/*.md
                                        ↓
                              defect-analysis（根因 + 指纹）
                                        ↓
                              defect-sync（本技能）
                                        ↓
                    ┌──────────┬──────────┬──────────┐
                    │  禅道    │  云效    │  自研    │
                    └──────────┴──────────┴──────────┘
```

---

## 快速使用

### 1. 配置环境变量

复制根目录 `.env.example` 中 **缺陷同步** 段落，填入真实值。

### 2. 预览映射（不推送）

```bash
cd defect-sync/scripts
python3 defect_sync.py preview ../../output/bugs/ --platform zentao
python3 defect_sync.py push ../../output/bugs/ --platform zentao --dry-run
```

### 3. 确认后推送

```bash
# Draft 状态草稿需加 --confirm
python3 defect_sync.py push ../../output/bugs/ --platform zentao --confirm

# 自研平台 Webhook
python3 defect_sync.py push ../../output/bugs/BUG-xxx.md --platform custom --confirm

# 仅推送 High/Critical
python3 defect_sync.py push ../../output/bugs/ --platform custom --confirm --severity High,Critical

python3 defect_sync.py push ../../output/bugs/ --platform zentao --confirm --notify
```

### 4. 检查配置

```bash
python3 defect_sync.py check --platform zentao
python3 defect_sync.py status
```

---

## 平台配置

| 平台 | `--platform` | 必需环境变量 |
|------|-------------|-------------|
| 禅道 | `zentao` | `ZENTAO_BASE_URL` `ZENTAO_ACCOUNT` `ZENTAO_PASSWORD` `ZENTAO_PRODUCT_ID` |
| 云效 | `yunxiao` | `YUNXIAO_ORG_ID` `YUNXIAO_PROJECT_ID` `YUNXIAO_PAT` |
| 自研/Webhook | `custom` | `DEFECT_WEBHOOK_URL`（可选 `DEFECT_WEBHOOK_TOKEN`） |

字段映射见 `config/platforms/*.json`，可按贵司平台字段自定义。

---

## pytest 自动同步（可选）

```bash
export DEFECT_SYNC=1
export DEFECT_SYNC_PLATFORM=custom      # zentao | yunxiao | custom
export DEFECT_SYNC_CONFIRM=1            # 允许推送 Draft 草稿
export DEFECT_SYNC_SEVERITY=High,Critical

./run_pytest.sh output/api_smoke.py -v
```

**默认行为**：
- 「环境」分流缺陷**不自动推送**
- 已同步过的指纹**跳过**（见 `output/bugs/sync_state.json`）
- 未设 `DEFECT_SYNC_CONFIRM=1` 时 Draft 草稿**不推送**

---

## 推送规则

| 规则 | 说明 |
|------|------|
| Draft → Confirm | 草稿默认不推送，需 `--confirm` 或人工改状态 |
| 指纹去重 | MD5(nodeid + 状态码 + 错误摘要)；**同批 push 仅首条**；历史见 sync_state.json |
| 环境分流跳过 | triage=「环境」的缺陷默认跳过 |
| 分析 enrichment | 读取 `output/reports/failure_analysis.json`，按 nodeid/指纹合并 category/confidence |
| sync_state.json | 记录 fingerprint → 远端 ID，防重复 |

---

## 飞书通知（可选）

推送成功后向飞书群发送摘要（需配置 Webhook）：

```bash
python3 defect_sync.py push ../../output/bugs/ --platform zentao --confirm --notify
```

| 环境变量 | 说明 |
|----------|------|
| `FEISHU_WEBHOOK_URL` | 飞书自定义机器人 Webhook |
| `FEISHU_NOTIFY_ON` | 通知级别过滤，如 `High,Critical` |

实现：`scripts/adapters/feishu.py`（Markdown 卡片，含 bug 标题、严重级别、链接占位）。

---

## AI 编辑器用法

```text
@defect-sync/SKILL.md

把 output/bugs/ 下已确认的草稿推到禅道，先 dry-run 给我看映射结果
```

```text
@defect-sync/SKILL.md

帮我对接公司自研缺陷平台，Webhook 地址在 .env 的 DEFECT_WEBHOOK_URL，
字段映射按 config/platforms/custom.json 改
```

---

## 文件结构

```
defect-sync/
├── SKILL.md                    # 本文件
├── config/platforms/
│   ├── zentao.json             # 禅道字段映射
│   ├── yunxiao.json            # 云效字段映射
│   └── custom.json             # 自研/Webhook 映射
└── scripts/
    ├── defect_sync.py          # CLI 入口
    ├── sync_service.py         # 同步主服务
    ├── canonical.py            # Markdown → Canonical JSON
    ├── sync_state.py           # 指纹 → 远端 ID
    └── adapters/
        ├── zentao.py
        ├── yunxiao.py
        ├── custom.py
```

---

## 与 bug-reporter 的分工

| 模块 | 职责 |
|------|------|
| `bug-reporter` | 缺陷**怎么写**（模板、严重级别、字段规范） |
| `defect-analysis` | 缺陷**怎么判**（根因、指纹、置信度） |
| `defect-sync` | 缺陷**怎么推**（对接外部工单系统） |

---

## 自研平台对接指南

1. 让后端提供 `POST /api/defects` Webhook，接收 JSON
2. 复制 `config/platforms/custom.json`，按字段名改 `field_map`
3. 设置 `DEFECT_WEBHOOK_URL` 和 `DEFECT_WEBHOOK_TOKEN`
4. `python3 defect_sync.py preview ... --platform custom` 验证映射
5. 确认后 `--confirm` 推送

若平台 API 与 Webhook 不同，可新增 `adapters/your_platform.py` 并在 `adapters/__init__.py` 注册。
