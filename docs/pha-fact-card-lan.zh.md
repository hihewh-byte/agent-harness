# Daily fact card · Mac + iPhone on the same Wi-Fi

> **Language / 语言**：[English](pha-fact-card-lan.md) · 中文（本文）

PHA **不是**医疗器械，**不提供**诊疗或处方。这张卡是你本机穿戴账本的每日快照。

给想用 **iPhone 事实卡**、而不是 Mac 对话框的 clone 用户。每日数字 **不走大模型**。Ollama 只在你点「Generate interpretation」时才需要。

## 为什么比 PHA 对话框好用

| | 事实卡 | `:8788` 对话框 |
|---|---|---|
| 每日习惯 | 捷径 / 锁屏导语 → Safari 完整卡 | 打开桌面页，再打字 |
| 第一次有数 | HealthKit 样本 + 相对**你自己**的规则三档 | 空库 + 先拉 4–5 GB 模型 |
| 数字 | Python 写入；模型改不了账本 | 对话有证据门，但仍要等回复 |
| 大模型 | 可选，在按钮后面 | 想聊出有用的话就必须有 |

仍然需要一台 Mac。iPhone **不**把健康 JSON 发到项目方服务器，只打到你局域网（或 Tailscale）上的这台机器。

## 你需要

- **Mac** 上跑着 PHA（`PHA_HOST=0.0.0.0`）
- 装了「健康」和「快捷指令」的 **iPhone**
- **同一 Wi-Fi**（手机用蜂窝打不到 `*.local` / 局域网 IP）
- Apple Watch 可选，但 HRV / 夜间睡眠通常来自手表
- Python 3.10+（与 [README Quick Start](../README.md#5-minute-quick-start-pha-app) 相同）

时间预期：已 clone 的话 Mac 约 5 分钟；第一次健康权限 5–10 分钟；之后交给自动化。

## 1. Mac

```bash
git clone https://github.com/hihewh-byte/agent-harness.git
cd agent-harness
bash scripts/bootstrap.sh
source .venv/bin/activate
bash scripts/macos/setup_fact_card_lan.sh
python -m pha.main
```

最后一个命令保持运行。开通脚本会：

- 把 `PHA_HOST` 设为 `0.0.0.0`（默认 `127.0.0.1` 只有 Mac 自己打得开）
- 若没有 `PHA_INGEST_TOKEN` 就写进 gitignored 的 `.env`
- 可选：把**已填好你本机地址和 token** 的 `pha-daily.shortcut` 签到 `data/local_shortcuts/`（gitignore，禁止拷进 git）

若 PHA 已经在听 `127.0.0.1`，改绑定后要重启：

```bash
bash scripts/pha_restart_accept.sh
```

**不要**把 `8788` 端口映射到公网。

## 2. iPhone（同一 Wi-Fi）

只要 **一条**捷径：**PHA Daily**（睡眠 + 健康包 + 打开事实卡）。自动化也只设一次。

**Clone 路径（文件里没有密钥）：**

1. iPhone **设置 → 快捷指令 → 高级 → 允许不受信任的快捷指令**
2. **设置 → 隐私与安全性 → 本地网络 → 打开「快捷指令」**
3. 下载 [`shortcuts/pha-daily.shortcut`](../shortcuts/pha-daily.shortcut)。导入时问两件事：
   - Mac 地址：`http://你的电脑.local:8788` 或 `http://<局域网IP>:8788`，**不要**填 `127.0.0.1`
   - Token：Mac `.env` 里的 `PHA_INGEST_TOKEN`（不要写进 git）
4. 跑一次 **PHA Daily**。健康 Find **每一项**都点允许访问。
5. **快捷指令 → 自动化 → 特定时间 → PHA Daily → 立即运行**。后台可能漏跑；以账本 `as_of` 为准。

Safari 应打开完整卡。HealthKit 还没入库时，页顶是开通清单；入库后是数字，以及相对你自己的三档一瞥（偏轻松 / 持平 / 偏好，**不是** 0–10 分）。

**已经跑过 Mac 开通脚本？** 可 AirDrop gitignored 的 `data/local_shortcuts/pha-daily.shortcut`（地址和 token 已填好）。不要上传这个文件。

系统锁屏通知只是导语。系统通知**不能**自定义点进 URL。要进完整卡：再跑一次 **PHA Daily**（或等 M2 App）。

## 3. Safari 连不上时

- 手机在 **Wi-Fi** 上，不是蜂窝；Mac 没睡眠，`python -m pha.main` 仍在跑
- macOS 防火墙允许了 Python / PHA
- 访客网络、AP 隔离、DHCP 换 IP 时，`.local` 经常挂。到捷径里改 **PHA Base** 为局域网 IP（或重新导入再填 URL）：

```bash
PHA_INGEST_URL_HOST=192.168.x.x bash scripts/macos/setup_fact_card_lan.sh
```

- 以后可选：两台都装 Tailscale，然后 `PHA_INGEST_URL_HOST=<tailscale 主机名或 IP>`

契约与单位：[healthkit-ingest.md](healthkit-ingest.md)（[English](healthkit-ingest.en.md)）。卡 JSON / 勾选：[pha-fact-card.md](pha-fact-card.md)（[English](pha-fact-card.en.md)）。

## Clone 不会自动给你的

- 公网 URL 或 App Store 安装包
- GitHub 捷径里的 Mac 地址或 ingest token（模板导入时再问；本机 `data/local_shortcuts/` 才带密钥，勿上传）
- 本版的 Garmin / CGM 厂商直连
- 替代苹果健康 App，或替代医生
