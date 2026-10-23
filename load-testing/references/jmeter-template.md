# JMeter 脚本模板

> **可运行模板**：`seckill_load.jmx`（与 `k6-template.js` 接口对齐）  
> **一键生成**：`./generate_jmeter.sh` → `output/seckill_load.jmx`  
> **一键执行**：`./run_jmeter.sh`（冒烟）或 `./run_jmeter.sh --full`

---

## 快速开始

```bash
# 1. 生成 jmx（从 references 复制到 output）
./generate_jmeter.sh

# 2. 冒烟（2 线程 / 10 秒，需 seckill_finance_system 在 5001）
./run_jmeter.sh

# 3. 正式压测
./run_jmeter.sh --full

# 自定义
TEST_BASE_URL=http://your-server:5001 THREADS=50 DURATION=300 ./run_jmeter.sh
```

---

## 完整示例（片段）

与 `references/seckill_load.jmx` 一致，含 HTTP Defaults、登录 token 关联、状态码断言。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="秒杀系统压测">
      <stringProp name="TestPlan.comments">seckill_finance_system</stringProp>
      <boolProp name="TestPlan.functional_mode">false</boolProp>
    </TestPlan>
    <hashTree>
      <Arguments guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables">
        <collectionProp name="Arguments.arguments">
          <elementProp name="HOST" elementType="Argument">
            <stringProp name="Argument.name">HOST</stringProp>
            <stringProp name="Argument.value">${__P(HOST,127.0.0.1)}</stringProp>
          </elementProp>
          <elementProp name="PORT" elementType="Argument">
            <stringProp name="Argument.name">PORT</stringProp>
            <stringProp name="Argument.value">${__P(PORT,5001)}</stringProp>
          </elementProp>
        </collectionProp>
      </Arguments>
      <hashTree/>
      <ConfigTestElement guiclass="HttpDefaultsGui" testclass="ConfigTestElement" testname="HTTP Request Defaults">
        <stringProp name="HTTPSampler.domain">${HOST}</stringProp>
        <stringProp name="HTTPSampler.port">${PORT}</stringProp>
        <stringProp name="HTTPSampler.protocol">http</stringProp>
      </ConfigTestElement>
      <hashTree/>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="商品列表并发线程组">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <stringProp name="ThreadGroup.num_threads">${__P(THREADS,10)}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">${__P(RAMP_TIME,10)}</stringProp>
        <boolProp name="ThreadGroup.scheduler">true</boolProp>
        <stringProp name="ThreadGroup.duration">${__P(DURATION,60)}</stringProp>
      </ThreadGroup>
      <hashTree>
        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="商品列表">
          <stringProp name="HTTPSampler.path">/api/products</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
        </HTTPSamplerProxy>
        <hashTree>
          <ResponseAssertion guiclass="AssertionGui" testclass="ResponseAssertion" testname="状态码断言">
            <collectionProp name="Asserion.test_strings">
              <stringProp name="49586">200</stringProp>
            </collectionProp>
            <stringProp name="Assertion.test_field">Assertion.response_code</stringProp>
            <stringProp name="Assertion.custom_message">商品列表请求失败</stringProp>
          </ResponseAssertion>
          <hashTree/>
        </hashTree>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
```

> **关于 `Asserion.test_strings`**：这是 JMeter 源码中的历史属性名（少了一个 `t`），写入 `.jmx` 时必须用 `Asserion`，写成 `Assertion.test_strings` 反而会导致断言不生效。

---

## 关键配置说明

| 配置项 | 说明 | 示例值 / 属性 |
|--------|------|----------------|
| num_threads | 线程数（并发用户） | `${__P(THREADS,10)}` |
| ramp_time | 爬坡时间（秒） | `${__P(RAMP_TIME,10)}` |
| duration | 持续时间（秒） | `${__P(DURATION,60)}` |
| scheduler | 启用调度器 | true |
| on_sample_error | 采样错误处理 | continue |
| HOST / PORT | 被测服务 | `-JHOST=127.0.0.1 -JPORT=5001` |

---

## CSV 参数化

```xml
<CSVDataSet guiclass="TestBeanGUI" testclass="CSVDataSet" testname="用户数据 CSV">
  <stringProp name="delimiter">,</stringProp>
  <stringProp name="filename">output/users.csv</stringProp>
  <boolProp name="ignoreFirstLine">true</boolProp>
  <boolProp name="recycle">false</boolProp>
  <stringProp name="shareMode">shareMode.thread</stringProp>
  <stringProp name="variableNames">username,password</stringProp>
</CSVDataSet>
```

> CSV 由 `data_factory` 导出，列为 `username, password`（明文）。多用户场景 **recycle=false**，线程数 ≤ CSV 行数。

---

## JSON 提取器（登录 token 关联）

```xml
<JSONPostProcessor guiclass="JSONPostProcessorGui" testclass="JSONPostProcessor" testname="提取 token">
  <stringProp name="JSONPostProcessor.referenceNames">token</stringProp>
  <stringProp name="JSONPostProcessor.jsonPathExprs">$.token</stringProp>
  <stringProp name="JSONPostProcessor.match_numbers">0</stringProp>
</JSONPostProcessor>
```

后续请求 Header Manager：

```xml
<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="Bearer Token">
  <collectionProp name="HeaderManager.headers">
    <elementProp name="" elementType="Header">
      <stringProp name="Header.name">Authorization</stringProp>
      <stringProp name="Header.value">Bearer ${token}</stringProp>
    </elementProp>
  </collectionProp>
</HeaderManager>
```

---

## 与 k6 模板对照

| 场景 | k6 | JMeter（seckill_load.jmx） |
|------|-----|---------------------------|
| 健康检查 | GET `${HEALTH_PATH}` | 健康检查 sampler |
| 登录 | POST `/api/auth/login` | 登录 + JSONPostProcessor |
| 商品列表 | GET `/api/products` | 商品列表 sampler |
| Profile | GET `/api/auth/profile` + Bearer | Profile + HeaderManager |
