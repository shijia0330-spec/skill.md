---
kind: jmeter_test
base_url: http://your-server:5001  # 被测系统地址
threads: 50                         # 并发线程数（建议 = users.csv 数据行数）
duration: 60                        # 压测持续时间（秒）
ramp_time: 10                       # 爬坡时间（秒）
data_source:                        # CSV 数据源（从 data_factory 导出）
  file: output/users.csv
  variables: [username, password]
  delimiter: ","
  ignore_first_line: true
  recycle: false
  share_mode: thread
endpoints:
  # 登录端点（auth: login 表示登录，自动提取 token）
  - name: 登录
    method: POST
    path: /api/auth/login
    json_body:
      username: "${username}"
      password: "${password}"
    expect_status: 200
    auth: login

  # 业务端点（auth: bearer 表示需要 Bearer Token）
  - name: 商品列表
    method: GET
    path: /api/products
    expect_status: 200
    weight: 5

  - name: 用户信息
    method: GET
    path: /api/auth/profile
    expect_status: 200
    weight: 3
    auth: bearer

  - name: 创建商品
    method: POST
    path: /api/products
    json_body:
      name: "JMeter压测商品"
      price: 99.99
      stock: 100
    expect_status: 201
    weight: 1
    auth: bearer
---

# JMeter 压测脚本模板

自动从 spec 定义生成可执行的 JMX 脚本。

## 用法

**先造数**（见 `templates/data_factory.md`），再生成 JMX：

```bash
python3 codegen/run_spec.py templates/data_factory.md -o output/data_factory.py
cd output && python3 data_factory.py && cd ..
wc -l output/users.csv   # 数据行数 N（不含表头），设 threads = N

python3 codegen/run_spec.py templates/jmeter_test.md -o output/api_load.jmx

jmeter -n -t output/api_load.jmx \
  -JHOST=127.0.0.1 -JPORT=5001 \
  -JTHREADS=50 -JDURATION=60 \
  -l output/results.jtl -e -o output/jmeter-report/
```

## 从 OpenAPI 导入

```bash
# 先导入 OpenAPI 生成 spec，再修改 kind 为 jmeter_test
python3 codegen/run_spec.py --import-openapi openapi.json -o output/imported_spec.md

# 修改 imported_spec.md，把:
#   kind: api_pytest
# 改成:
#   kind: jmeter_test
# 再生成 JMX:
python3 codegen/run_spec.py output/imported_spec.md -o output/api_load.jmx
```

## 默认参数

| 参数 | 环境变量 | JMeter 属性 | 默认值 |
|------|---------|------------|--------|
| Host | - | HOST | your-server |
| Port | - | PORT | 5001 |
| 线程数 | - | THREADS | 50 |
| 持续时间 | - | DURATION | 60 |
| 爬坡时间 | - | RAMP_TIME | 10 |

## auth 字段说明

| 值 | 含义 | 生成逻辑 |
|-----|------|---------|
| `login` | 登录端点 | 添加 JSON Header + JSON Extractor 提取 token |
| `bearer` | 需 Bearer Token | 添加 `Authorization: Bearer ***` Header |
| 不填 | 无需鉴权 | 不加 Header |

## CSV 数据源（与 data_factory 衔接）

通过 `data_source` 配置段，JMeter 可从 data_factory 导出的 CSV 读取测试数据：

```yaml
data_source:
  file: users.csv
  variables: [username, password]   # 列顺序须与 CSV 一致（username 在前）
  delimiter: ","
  ignore_first_line: true           # CSV 有表头时必须 true
  recycle: false                    # 多用户：每线程一账号，不循环
  share_mode: thread                # 每线程独立读一行
```

**完整流程：**

```
1. data_factory 造 N 个用户 → users 表 + output/users.csv（username, password）
2. threads = N（或 ≤ N）
3. JMeter 读取 users.csv → 每线程不同账号登录
4. 压测业务端点
5. 清理 → data_factory --cleanup
```

**登录端点使用 CSV 变量：**

```yaml
endpoints:
  - name: 登录
    json_body:
      username: "${username}"
      password: "${password}"
```

> 勿用 `${password_hash}` — 登录 API 要明文密码，hash 仅存在 DB 中。
