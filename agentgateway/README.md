# AgentGateway 配置导出

这些 JSON 由 `scripts/export-public-gateway-config.py` 从生产网关导出，时间以仓库里对应提交的时间为准。

| 文件 | 内容 |
| --- | --- |
| `providers.json` | 上游 provider：协议类型与格式、baseUrl；凭据只以 `$VAR` 形式出现 |
| `models.json` | 对外暴露的模型名，以及每个模型指向的 provider |
| `virtual-models.json` | 虚拟模型与故障转移目标 |
| `model-catalog.json` | 计费使用的参考价格表 |

导出方式（在部署 AgentGateway 的那台机器上执行）：

```sh
python3 scripts/export-public-gateway-config.py --out /tmp/public-export
```

脚本只读，不会修改生产配置。它在下列情况下拒绝导出：

- 出现白名单之外的资源类型：存放用户密钥的 `llm.apiKey`、含 CORS 允许列表的 `llm.policy` 永远不导出
- 任何 key / token / secret 字段不是 `$VAR` 引用
- 任何字段里出现形如 `sk-…`、`nc_ai_…`、`hskey-…` 的原始密钥

内网地址不会出现在这些文件里：导出时 Tailnet 域名被替换为 `<internal-host>`，私网与 CGNAT IP 被替换为 `<internal-ip>`；替换后如果仍能匹配到内网地址，脚本会拒绝写出文件。回环地址 `127.0.0.1` 保留，因为它只描述网关到本机 CLIProxyAPI 的这一跳。
