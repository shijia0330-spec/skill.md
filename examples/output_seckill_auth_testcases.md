# 秒杀财务系统 · 用户认证 测试用例

## 文档信息

- 依据需求：`examples/prd_mini_seckill_auth.md`
- 生成版本：规则 1.2.0（skills V3.0 · testcase-skills/生成）
- 测试范围：注册 / 登录 / Profile / 鉴权失败；不含商品与秒杀
- 结构说明：标准 3 级（模块 → 场景 → 检查点）
- 待澄清汇总：1 条

## 需求追溯表

| 需求段落 | 用例编号 | 说明 |
|----------|----------|------|
| 2.1.1 用户注册 | C-01～C-03, V-01～V-03 | 正向 + 校验 + 重复用户名 |
| 2.1.2 用户登录 | L-01～L-02, V-04 | 成功取 Token、错误密码 |
| 2.1.3 用户信息 | D-01～D-02 | 有 Token / 无 Token |
| 2.1.4 权限 | P-01 | admin 与 customer 角色字段（Profile） |

## 核心流程测试

### F-01 新用户注册并登录查 Profile

```
- 访客调用 POST /api/auth/register（合法 username/password/email）
  - 预期：HTTP 201，返回用户标识或成功语义
- 使用新账号 POST /api/auth/login
  - 预期：HTTP 200，响应含 JWT（access_token 或 token 字段）
- 携带 Bearer Token GET /api/auth/profile
  - 预期：HTTP 200，username 与注册一致，role 为 customer
```

## 详细功能点测试

### 用户注册

#### C-01 合法三字段注册成功

- 提交唯一 username、password≥6、合法 email
- 响应 201；库中角色为 customer，密码非明文

#### C-02 仅必填 username+password 注册成功

- email 省略或空
- 响应 201（若产品允许无邮箱）

#### V-01 用户名为空拒绝注册

- username 为空或全空白
- 响应 4xx；不创建用户

#### V-02 密码少于 6 位拒绝注册

- password 长度为 5
- 响应 4xx；错误信息指明密码规则

#### V-03 重复用户名拒绝注册

- 已存在 username 再次注册
- 响应 400（或 409）；提示用户名已存在

### 用户登录

#### L-01 正确凭证登录返回 JWT

- admin / admin123 调用 POST /api/auth/login
- HTTP 200；Token 可用于后续 Profile

#### V-04 错误密码登录失败

- 正确 username + 错误 password
- HTTP 401；响应体不含有效 Token

### 用户信息 Profile

#### D-01 携带有效 Token 查询 Profile

- Header：`Authorization: Bearer <token>`
- HTTP 200；含 username、role

#### D-02 未带 Token 访问 Profile 被拒绝

- 无 Authorization 头
- HTTP 401

### 权限（Profile 字段）

#### P-01 管理员 Profile 角色为 admin

- admin 登录后 GET /api/auth/profile
- role 字段为 admin（与普通 customer 区分）

## 用例评审表

| 编号 | 名称 | 优先级 | 类型 | 标签 |
|------|------|--------|------|------|
| C-01 | 合法三字段注册成功 | P0 | smoke_sanity | auth,register |
| C-02 | 仅必填注册成功 | P1 | functional | auth,register |
| V-01 | 用户名为空 | P1 | functional | validation |
| V-02 | 密码过短 | P1 | functional | validation |
| V-03 | 重复用户名 | P1 | regression | auth,register |
| L-01 | 正确登录 JWT | P0 | smoke_sanity | auth,login |
| V-04 | 错误密码 401 | P1 | security | auth,login |
| D-01 | Token 查 Profile | P1 | functional | auth,profile |
| D-02 | 无 Token 401 | P1 | security | auth,profile |
| P-01 | admin 角色 | P1 | functional | rbac |

## 通用覆盖矩阵自检

| 维度 | 触发 | 覆盖 |
|------|------|------|
| A 正向主路径 | 是 | C-01, L-01, D-01 |
| B 反向/异常 | 是 | V-01～V-04, V-03 |
| C 边界 | 是 | V-02（长度边界） |
| D 权限 | 是 | P-01, D-02 |
| E 数值/次数 | 否 | — |
| F 状态/时间 | 否 | — |
| G 集成依赖 | 部分 | T-01 |
| H API 契约 | 可选 | 有 openapi.yaml 时补状态码 |

## 待澄清清单

| # | 问题 | 关联编号 |
|---|------|----------|
| T-01 | 注册无 email 时接口返回 201 还是 400？ | C-02 |
