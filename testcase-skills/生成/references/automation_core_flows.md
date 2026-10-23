# 自动化用例 · 核心流程

> 端到端流程须先列树，再拆 API / UI 检查点。默认示例：**秒杀财务**。

## 流程 1：注册 → 登录 → Profile（API）

见 `examples/output_seckill_auth_testcases.md` 核心流程节。

| 步 | 动作 | 自动化对接 |
|----|------|------------|
| 1 | POST `/api/auth/register` | `api-skills` case |
| 2 | POST `/api/auth/login` | Token 写入变量池 |
| 3 | GET `/api/auth/profile` | Bearer 断言 |

## 流程 2：登录 → 商品列表（UI）

见 `testcase-skills/UI精简/SKILL.md` · UI-SECKILL-02 / UI-SECKILL-06。

浏览器步骤须可解析（`step_vocabulary.md`），转化后走 `UI-skills/转化`。

## 铺底（seed）

```bash
curl -X POST "http://your-server:5001/api/test/init" -H "Content-Type: application/json" -d '{}'
```

重复注册、列表有数据等 case 须在文档头标注 **seed** 依赖。
