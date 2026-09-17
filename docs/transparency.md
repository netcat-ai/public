# 网关透明度说明

本文说明 Netcat 的 AI 网关（入口域名 `ai.tiny.yun`）如何处理请求。文中的"已验证"指有直接观测数据支撑，"待确认"指还没有最终结论，我们不会把它们写成已完成。

## 请求路径

```text
客户端 → ai.tiny.yun（AgentGateway）
       → 本机 CLIProxyAPI 或直连第三方 provider
       → 上游模型服务
```

路由关系不在文档里重复描述，直接看 `agentgateway/providers.json` 和 `agentgateway/models.json`：每个对外模型名指向哪个 provider、每个 provider 的上游地址和协议格式都写在里面。这些文件由脚本从生产导出，不是手写的说明。

## 支持的协议

同一套模型按客户端协议分入口：

| 入口 | 协议 |
| --- | --- |
| `/v1/chat/completions` | OpenAI Chat Completions |
| `/v1/responses` | OpenAI Responses |
| `/v1/messages` | Anthropic Messages |
| `/v1beta/models/...:generateContent`、`:countTokens` | Gemini 原生 |

个别模型只在上游的某一种协议下提供，例如 Grok 4.6 只能走 `/v1/responses`，用 chat 协议调用会被网关拒绝，错误是 `unsupported conversion`。

## 记录了什么

网关把每次请求的元数据写入自己的日志库（`agentgateway_logs.request_logs`）：

时间、耗时、HTTP 状态、错误摘要、provider、模型名、输入/输出 token 数、参考成本、调用方标识（用户与分组）、客户端 User-Agent 名称。

截至 2026-09-17 的实测：日志库共 12,326 条请求记录，`has_payload` 全部为 false，内容表 `request_log_payloads` 为 0 行，也就是说**网关自身没有存储 prompt 或模型回答的内容**。

保留时长：目前**没有设置自动清理**。日志从 2026-09-03 开始记录，每天都有数据，服务上也没有配置任何清理任务，所以在写下这句话的时点，这些元数据会一直保留。我们正在确定一个明确的保留期限，定了会更新本页。

## 已知问题

CLIProxyAPI（网关本机 8317 端口的上游聚合服务）会在请求失败时写出错误日志文件，位置是运行节点本地的 `/opt/netcat/cliproxyapi/logs/`，文件名形如 `error-v1-responses-2026-09-17T160614-ca752292.log`。实测这些文件里包含请求内容片段以及 `Authorization` 头。

这些文件目前同样没有上限：配置里 `logs-max-total-size-mb` 与 `error-logs-max-files` 都没有设置，也没有 logrotate。写下这句话时是 10 个文件、约 3.7 MB。

这与上面"网关不落内容"的说法不冲突——网关自己的日志库确实不含内容——但对"你的内容不会留在我们服务器上"这个更宽的说法是有影响的。

处理计划：改用不含请求体的错误日志，或者为它设置明确的上限与保留期限，然后在本页更新。在完成之前，请不要把这一页理解为"任何地方都不留存内容"。

## 计费

网关按请求的 token 数乘以参考价格计算成本，参考价格表见 `agentgateway/model-catalog.json`。这一列是**参考成本**，面向会员的展示价格由站点侧在此基础上换算得到。

## 待确认清单

- 日志保留天数（网关日志库与 CLIProxyAPI 错误日志）
- CLIProxyAPI 错误日志的处理方式

## 不在公开范围的内容

以下属于内部运营数据，不随本仓库公开：面向会员的价格换算倍率、限额与熔断策略的具体数值、服务器地址与访问方式、用户数据。需要这些信息时请通过支持渠道联系我们。
