# 多栈代码生成（按仓库真实栈来）

有的仓是 Python pytest，有的是 Node Jest，还有的要导出 Postman 集合给业务先点点看。生成前**先看仓库里到底用什么**，别默认一套。

---

## 1. 一般流程

1. 扫一眼 **`package.json` / `requirements.txt` / `pyproject.toml`**，判断主语言。  
2. 从测试计划里拿出接口列表和用例意图。  
3. 调对应的生成器（Jest、pytest、Postman 等——以你们实现为准）。  
4. 生成完跑一遍静态检查或试编译，避免语法都过不去。

---

## 2. 常见产出

| 目标 | 用途 |
|------|------|
| pytest / requests | Python 服务最常见 |
| Jest / Vitest | 前端或 BFF 用 JS 测 HTTP 时 |
| Postman Collection | 给人工探索、评审契约 |

**说明**：浏览器 E2E 走 **UI-skills**，这里只管 HTTP 层。

若当前仓库走「Markdown spec → pytest」（`generate.sh` / `codegen/run_spec.py`），接口脚本区分 **`cases`**（单步多条测试）与 **`scenarios`**（单函数内多步串联）；细则见 **`02_测试脚本生成.md`** 第 6 节。

---

## 3. 纪律

- 生成前先看栈；生成后必须能校验（语法或 lint）。  
- 用例 id 和计划对应，方便报告对照。  
- 别把两种栈默认混在一个仓库里瞎生成。
