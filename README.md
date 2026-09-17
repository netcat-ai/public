# netcat-ai/public

这里放 Netcat 私云对外可以公开的内容，目的是让使用者能自己核对服务怎么工作，而不是只看宣传。

## 现在有什么

| 目录 | 内容 |
| --- | --- |
| `agentgateway/` | 从生产 AgentGateway 导出的可公开配置：上游 provider、模型清单、虚拟模型、计费参考价格表 |
| `scripts/` | 导出脚本。按白名单导出，并在写出任何文件前拒绝未脱敏的凭据 |
| `docs/` | 说明文档：[请求架构](docs/architecture.md)、[透明度说明](docs/transparency.md) |

## 这些文件为什么可信

`scripts/export-public-gateway-config.py` 从生产网关的管理接口读取配置，只保留白名单内的资源类型，并在写文件之前逐个字段检查：任何不以 `$` 开头的 key / token / secret 字段，或任何形如原始密钥的字符串，都会让它直接报错退出、不产出文件。所以这里永远不该出现可用凭据，凭据只在服务器上，配置里只保留 `$VAR` 引用。内网地址同样在导出阶段就被替换成占位符：Tailnet 域名写成 `<internal-host>`，私网与 CGNAT IP 写成 `<internal-ip>`，如果替换后仍有残留，脚本会拒绝写出文件。

文件的新旧可以看 git 提交时间；导出命令和范围见 `agentgateway/README.md`。

## 不在这里的东西

服务器地址与登录方式、网络拓扑细节、任何形式的密钥、用户数据、内部运维与回滚记录。这些属于私云内部信息，不随本仓库公开。
