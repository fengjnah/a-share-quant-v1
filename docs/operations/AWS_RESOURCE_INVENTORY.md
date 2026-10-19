# AWS 部署资源与配置变更清单

> 记录基准：2026-10-19（北京时间）；整理时间：2026-10-20。
>
> **证据边界：** 本文根据部署验收记录、用户提供的 AWS 账单摘要及运行验收证据整理，不是通过 AWS API 对整个账户进行的实时全资源盘点。未直接核验的项目明确标注“待控制台/服务器复核”。不得把未知资源认定为不存在。

## 1. 摘要

- AWS 区域：东京（ap-northeast-1；根据现有实例/账单记录）。
- 实例：Linux EC2 **t3.micro**。
- 公网入口：https://54.95.115.109/quant/。
- 应用：Nginx 反向代理 + Streamlit 研究工作台；保留原有 Java HTTP 服务。
- 当前部署代码：GitHub main SHA **59ce53999477ad898a2428679f19694b48f03005**。
- 当前 release 目录：/opt/a-share-quant-workbench/releases/59ce53999477ad898a2428679f19694b48f03005。
- 数据库：/var/lib/a-share-quant-workbench/workbench.sqlite3，当前只有迁移记录，没有实际行情历史。
- TLS：Let's Encrypt 证书，Certbot 5.8；使用 IP SAN，证书记录有效期截至 **2026-10-25 23:17:40（北京时间）**。
- 当前生产部署不包含尚未合并的 PR #29 更新保护脚本；实际版本切换与回滚尚未完成真实演练。
- 不连接交易账户、不自动下单；云端行情库为空，在线采集和数据授权门禁关闭。

## 2. AWS 资源清单

| 资源 | 当前已知配置/状态 | 证据与注意事项 |
|---|---|---|
| AWS 区域 | 东京区域（ap-northeast-1） | 来自现有实例/账单记录；建议在控制台复核 |
| EC2 | Linux t3.micro | 用户提供账单记录；实例身份另有 IMDS 核验记录 |
| 公网 IPv4 | 54.95.115.109 | 当前 HTTPS 入口；公网 IPv4 计费样本约 $0.005/小时 |
| EBS 系统盘 | gp3，分配 8 GiB | 账单样本用量 4.505 GB-Mo；需在控制台复核卷 ID、挂载和快照 |
| 安全组 | 用户确认允许入站 TCP 443 后公网 HTTPS 验收通过；TCP 80 用于现有 HTTP 路由/HTTP-01 验证 | 未获得完整安全组规则导出；22、80、443 的来源 CIDR 应在控制台核对，避免将 SSH 暴露给所有地址 |
| DNS / 域名 | 当前以公网 IP 访问，没有依赖自有域名的证据 | 证书 SAN 包含 IP 54.95.115.109 |
| S3、快照、额外 EIP、负载均衡、CloudWatch 等 | 本次资料未证明存在或不存在 | 必须通过 AWS 控制台/CLI 做账户级盘点；不能根据账单样本为 $0 就断言无资源 |

### 2.1 费用参考（不是完整账户账单）

用户提供的账单样本：

| 项目 | 样本值 | 备注 |
|---|---:|---|
| EC2 t3.micro | 420.959 小时，$5.73 | 样本已被抵扣 |
| EBS gp3 | 4.505 GB-Mo，$0.43 | 实例分配 8 GiB |
| 公网 IPv4 | 423 小时，$2.12 | 样本已被抵扣 |
| 样本合计 | 抵扣前 $8.28；Credits -$8.28；现金 $0 | 账期不明确，不可直接外推为整月实账 |
| 固定配置月度估算 | 约 $14.35 / 730 小时 | 计算：$0.0136×730 + $0.096×8 + $0.005×730；不含未知额外费用、税费及流量变化 |

现有记录中的 Credits 余额为 $65.22，Free plan 预计剩余约 65 天；确切计划到期、Credits 自身条款及完整账户费用尚未独立读取。不要将该估算当成 AWS 账单或保证免费运行。建议在 Billing 控制台确认计划、额度、完整账期及费用提醒；此前 $5/$10 Budget 提醒尚未配置。

## 3. EC2 上的目录与文件

### 3.1 应用与 release

| 路径/服务 | 用途 | 状态 |
|---|---|---|
| /opt/a-share-quant-workbench/releases/59ce53999477ad898a2428679f19694b48f03005 | 当前部署代码的版本化 release 目录 | 已核验；53 个 src/deploy/项目配置文件的 Git blob SHA 与目标版本匹配 |
| a-share-quant-workbench.service | Streamlit 研究工作台 systemd 服务 | active；已启用自动启动 |
| Streamlit 监听地址 | 127.0.0.1:8513 | 仅本机回环，不应对公网开放 |
| Streamlit 资源限制 | 内存上限 240 MiB；CPU 配额 20% | 当前服务配置记录 |
| 原有 Java 服务 | PID 26015；HTTP 8080 | 验收时保持运行；内部 HTTP 200。PID 会变化，维护时应通过服务管理器核验，不要依赖固定 PID |
| Nginx | 公网入口、TLS、Basic Auth、路径代理 | active；保留原有 / → 8080 路由 |
| Nginx 日志 | 每日轮转，保留 14 份 | 现有配置记录；具体日志文件路径需在服务器核验 |
| 研究服务日志 | systemd journal 限制 20 MiB / 14 天 | 现有配置记录；未更改 Java/系统日志策略 |

### 3.2 持久化数据库与备份

| 路径 | 用途 | 状态 |
|---|---|---|
| /var/lib/a-share-quant-workbench/workbench.sqlite3 | 云端研究工作台 SQLite 数据库 | 7 张表；只有 schema_migrations 有 2 行，其余 0 行 |
| /var/lib/a-share-quant-workbench/backups/20261019T143606-874f32c73a39.sqlite3 | 2026-10-19 在线备份 | 逐表内容校验与源库一致 |
| 数据目录权限 | 目录 700；数据库文件 600 | 当前部署记录 |
| 生产行情数据 | 无实际行情历史 | 不要把本地临时 Demo 数据库当作云端生产库；当前云端数据库只是结构底座 |

数据库放在 release 目录外，是为了代码版本更新时不随旧版本目录一起删除。当前并未实现本地 PC 与 AWS SQLite 的自动同步，也没有确认生产级自动备份保留策略。不要直接覆盖正在运行的 SQLite 文件；若将来同步，应通过经认证的接口和事务批次写入。

## 4. Nginx、端口和访问保护

| 项目 | 作用/现状 |
|---|---|
| TCP 443 | 公网 HTTPS 入口；用户手机已确认可登录访问 |
| TCP 80 | HTTP 入口；用于现有 Java HTTP 路由，并提供 Let's Encrypt HTTP-01 webroot 验证；不能未经检查就关闭 |
| TCP 22 | SSH 管理通常使用此端口；实际安全组来源规则需控制台核验 |
| TCP 8513 | Streamlit 仅监听 127.0.0.1，不应在安全组开放 |
| TCP 8080 | 原有 Java 服务内部 HTTP 端口；公网是否可达需复核安全组与监听地址 |
| /quant/ | 手机研究工作台入口，经过 Nginx 认证与代理 |
| / | 保留原有 Java 服务代理至 8080 |
| Basic Auth | 研究页面、静态资源和 Streamlit 路径均受保护；未登录/错误口令返回 401 |
| WebSocket | 未登录 401；登录后 101，并协商 streamlit 子协议 |
| TLS | 公网严格 TLS 校验成功；手机登录后的 M1/M2/M3 切换经用户确认 |

Basic Auth 凭据保存在用户本机私有文件：
C:/Users/iyoyi/.config/a-share-quant-workbench/phone-access.txt。

**安全要求：** 不要将用户名/密码、私钥、证书私钥、AWS 凭据或该凭据文件内容写入 GitHub。此清单不包含任何秘密。若凭据曾被提交或公开，应立即轮换。

## 5. TLS 证书与 Certbot

| 项目 | 当前记录 |
|---|---|
| CA | Let's Encrypt YE1 |
| 证书标识 | SAN 包含 IP 54.95.115.109 |
| TLS 版本 | TLS 1.3 验证通过 |
| 有效期 | 2026-10-19 07:17:41 至 2026-10-25 23:17:40（北京时间） |
| SHA-256 | 7139a47f5a598a811f313faa9adbb63894c946bdef2f467b1c58a4340a84b5da |
| Certbot | 5.8 |
| 签发/验证 | 生产 ACME；webroot；shortlived profile；HTTP-01 |
| HTTP-01 webroot | /var/www/quant-acme |
| 自动续期定时器 | quant-cert-renew.timer，每天检查两次 |
| 续期后处理 | deploy hook 测试并重载 Nginx |
| 验收限制 | 已观察到两次续期检查成功；证书当时尚未到续期时间，未完成真实到期续签演练 |

证书免费，但 EC2、EBS、公网 IPv4 和流量等资源仍可能计费。到期日临近时，应检查 timer、服务日志、certbot renew --dry-run 及 hook 行为，并验证公网实际提供的证书。不要通过 --force-renewal 做日常测试。

常用只读检查：

    date
    sudo certbot --version
    sudo certbot certificates
    sudo systemctl status quant-cert-renew.timer --no-pager
    sudo systemctl list-timers --all | grep -E 'certbot|quant-cert-renew'
    sudo journalctl -u quant-cert-renew.service --since "7 days ago" --no-pager
    sudo nginx -t

续期预演（需要确认当前配置后执行）：

    sudo certbot renew --dry-run

预演通过不等于生产证书已更新，也不等于 hook 已经在真实续期时成功。

## 6. 本次部署/配置变更明细

| 变更项 | 增加/修改内容 | 状态/边界 |
|---|---|---|
| EC2 公网访问 | 用户确认允许安全组 TCP 443 | 修改已生效，随后 HTTPS 验收通过；完整安全组规则未导出 |
| Nginx HTTPS | 为公网 IP 配置 TLS 入口并接入证书 | 公网严格 TLS 验证通过 |
| Nginx 路径代理 | 增加/配置 /quant/ 研究工作台路径 | 与原 / → Java 8080 路由共存 |
| Basic Auth | 保护研究页面、静态资源、Streamlit 路径和 WebSocket 握手 | 用户手机登录验收通过 |
| Streamlit 服务 | systemd 服务；本机监听 8513；内存 240 MiB、CPU 20% 限制 | active 且启用自启动 |
| SQLite 持久化 | 使用 release 外的云端数据库路径，目录 700、文件 600 | 当前仅 schema_migrations 有 2 行 |
| SQLite 备份 | 新增 2026-10-19 在线备份并逐表校验 | 本次已验证源/备份一致 |
| Certbot | 安装/配置 Certbot 5.8、HTTP-01 webroot 和每日两次续期检查 | 检查运行过；真实到期续期仍未演练 |
| Nginx/研究服务日志 | Nginx 每日轮转 14 份；研究服务 journal 20 MiB/14 天 | 未改变 Java/系统日志策略 |
| 生产应用版本 | 部署 main SHA 59ce53999477ad898a2428679f19694b48f03005 | 与当时 main 匹配 |
| 保护式更新脚本 | PR #29 提供在线备份、内容检查、拒绝隐式迁移、依赖检查、资源约束和失败回滚 | **PR #29 未合并；没有用于真实生产版本切换；真实回滚未验收** |
| AWS 新建资源 | 本次记录称未创建新的 AWS 资源、未更改实例/磁盘容量或计费计划 | 仅代表此次部署任务记录；账户级其他资源仍需盘点 |
| 生产行情采集 | 未启用；授权门禁关闭 | 未执行真实在线采集 |
| M4/M5 | 未部署 | 当前线上只有 main 已合并的 M1/M2/M3 与项目进度入口 |

## 7. 当前线上功能与明确限制

- 线上入口：https://54.95.115.109/quant/。
- 已验证：TLS、Basic Auth、登录后的 M1/M2/M3 页面切换、Streamlit WebSocket、内部健康检查。
- 代码：main SHA 59ce53999477ad898a2428679f19694b48f03005。
- 未部署：未合并的 M4/M5。
- 数据限制：云端行情库为空；图表/情绪/持仓数据不足；没有真实全市场历史覆盖验收。
- 未完成：真实版本切换与回滚演练；真实到期续签演练；AWS 账户级全资源与完整账单盘点。
- 手机公网访问已由用户确认成功；SSH 私有隧道和 CSS 窄屏测试不替代真实手机验收。

## 8. 建议维护命令与检查清单

### 8.1 登录和基础状态

使用 PuTTY 通过 SSH 登录 EC2，用户名和私钥以实际 AMI/实例配置为准。首次连接核验 SSH 主机指纹。不要把私钥提交到仓库。

    hostname
    date
    timedatectl
    df -h
    free -h
    sudo systemctl status nginx --no-pager
    sudo systemctl status a-share-quant-workbench.service --no-pager
    sudo nginx -t

### 8.2 核验监听端口

    sudo ss -lntp

预期 Streamlit 只监听 127.0.0.1:8513；确认没有意外暴露内部端口。Java 服务和 Nginx 实际监听情况以命令输出为准。

### 8.3 数据库与备份

    sudo ls -ld /var/lib/a-share-quant-workbench
    sudo ls -l /var/lib/a-share-quant-workbench

维护前先确认备份状态、磁盘剩余空间和服务状态。不要手工删除 SQLite 的 -wal 或 -shm 文件，也不要覆盖正在使用的数据库。

### 8.4 AWS 控制台待复核

- [ ] EC2 实例 ID、区域、状态、AMI、实例类型和公网 IPv4。
- [ ] 安全组完整入站/出站规则，尤其 SSH 来源 CIDR、80/443 与内部端口。
- [ ] EBS 卷、挂载、快照和删除保护。
- [ ] 是否存在额外弹性 IP、快照、S3、负载均衡、CloudWatch、NAT 或其他收费资源。
- [ ] Billing 完整账期、Credits 条款、Free plan 截止时间和费用提醒。
- [ ] 证书实际到期时间、续期 timer、deploy hook 和公网证书是否一致。
- [ ] 最近备份是否成功、恢复演练是否完成。
- [ ] PR #29 是否已审查/合并；生产版本切换和回滚尚未真实验收。

## 9. 维护原则

1. **先核验再修改：** 本文不是实时状态接口；每次维护都应先检查服务器和 AWS 控制台当前状态。
2. **代码与数据分离：** release 目录可版本化切换；数据库、备份和凭据位于独立位置。
3. **不绕过安全门禁：** 不公开 8513/8080，不关闭 TLS 校验，不将 Basic Auth 密码写入仓库。
4. **备份先于破坏性操作：** 更新、迁移、删除或恢复前先备份并核验。
5. **测试不等于生产验收：** dry-run、离线测试、隧道测试和模拟回滚不能冒充真实续签、手机公网验收或生产回滚。
6. **不凭账单样本推断全账户：** 用 AWS Billing 与资源控制台核验完整账期和全部资源。

## 10. 相关链接

- [线上研究工作台](https://54.95.115.109/quant/)
- [GitHub 仓库](https://github.com/fengjnah/a-share-quant-v1)
- [PR #29：更新保护脚本（状态需实时核验）](https://github.com/fengjnah/a-share-quant-v1/pull/29)
- [AWS Free Tier plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
- [AWS Budgets 定价](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/)
- [Let's Encrypt short-lived certificates 说明](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)
