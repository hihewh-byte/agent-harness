# HealthKit ingest（M0）

把 iPhone「健康」里的 Watch 样本推到本机 PHA：`POST /ingest/healthkit`。  
**不是** zip 导入（那是 `POST /data/upload`）。Mac **不能**直连 Watch。

自检（假数据、临时库）：

```bash
python scripts/pha_healthkit_ingest_selfcheck.py
```

未绿这条，不得宣称「主动 Agent 已上线」。真机捷径（M0-P1）才算管道通。

---

## 0. 本机现状（2026-09-04）

已在 gitignored `.env` 配好并经官方 `scripts/pha_restart_accept.sh` 重启（launchd）：

| 项 | 值 |
|----|----|
| 监听 | `0.0.0.0:8788` |
| 本机名 | `http://WenhuideMacBook-Air.local:8788`（DHCP 换 IP 时仍可用） |
| 当前局域网 IP | 会变；2026-09-04 为 `192.168.77.125`（旧捷径里的 `192.168.77.21` 已失效，会 timeout） |
| Token | `.env` 的 `PHA_INGEST_TOKEN`（不要写进文档/不要 commit） |
| 时区 | `PHA_INGEST_TZ=Asia/Shanghai` |
| 健康权限 | **「PHA 同步健康」只请求步数（Steps）**，不要求 HRV/睡眠等 |

已签名捷径（含 URL + token，勿提交 git）：

- 桌面：`PHA ingest 探测.shortcut`
- 桌面：`PHA 同步健康.shortcut`（只读步数 → 计算成数字 → POST `user_id=default`）
- 生成脚本：`scripts/macos/build_pha_ingest_shortcuts.py`

iPhone 请删掉旧的「PHA 同步健康」再导入桌面新文件。若仍 timeout：设置 → 隐私与安全性 → 本地网络 → 打开「快捷指令」。

---

## 1. Mac 侧准备

1. 在 `.env` 设置（**不要**提交真实 token）：

```bash
PHA_INGEST_TOKEN='换成足够长的随机串'
PHA_INGEST_TZ=Asia/Shanghai
```

2. 默认 PHA 只绑 `127.0.0.1`，**手机打不到**。同一 Wi-Fi 或 Tailscale 时：

```bash
PHA_HOST=0.0.0.0
```

然后按现有方式重启 PHA。只把 ingest 暴露在你自己的网/VPN 里，不要对公网开放。

3. 探测：

```bash
curl -sS -X POST "http://<Mac的Tailscale或局域网IP>:8788/ingest/healthkit" \
  -H "Content-Type: application/json" \
  -H "X-PHA-Ingest-Token: $PHA_INGEST_TOKEN" \
  -d @scripts/fixtures/healthkit_ingest_sample.json
```

成功：`{"ok": true, "inserted": ..., "source": "healthkit", ...}`。  
无 token 配置 → 503；错 token → 401。

---

## 2. JSON 契约

```json
{
  "user_id": "default",
  "token": "可选；更推荐用 Header",
  "samples": [
    {
      "metric_type": "hrv",
      "timestamp": "2026-08-30T08:15:00+08:00",
      "value": 42.0,
      "unit": "ms",
      "source": "healthkit"
    }
  ]
}
```

| 字段 | 规则 |
|------|------|
| `metric_type` | v1：`hrv` `rhr` `steps` `sleep_hours` `active_energy`。也接受常见 HealthKit 类型名。未知类型：**丢该样本**，不猜测。 |
| `timestamp` | ISO-8601。按 `PHA_INGEST_TZ` 落到本地日历日。无法解析 → **整批丢弃**（400）。 |
| `value` | 有限数字。单位见下表，**v1 不做换算**。 |
| `source` | 必须是 `healthkit`。 |
| 鉴权 | Header `X-PHA-Ingest-Token` 或 body `token`。 |

**单位（Shortcuts 里先换好再 POST）：**

| 指标 | 值 |
|------|----|
| `hrv` | 毫秒（SDNN）。健康 App 有时是秒，须 ×1000。 |
| `rhr` | bpm |
| `steps` | 当日步数（建议每天一条累计，不要把同一累计值按小时重复 POST） |
| `sleep_hours` | **小时**（不是秒） |
| `active_energy` | kcal |

幂等键：`healthkit|{user}|{metric}|{本地时间iso}|healthkit`。同一秒同一指标重复推送会被 `INSERT OR IGNORE`。

---

## 3. iPhone 捷径（M0-P1）

优先用桌面上已签名的 **「PHA 同步健康」**（不必手搭）。iPhone 与 Mac 同一 Wi-Fi，打开捷径 → 允许健康 → 运行。

若要手搭，步骤如下。

1. 打开 **捷径** → 新捷径，名称如 `PHA 同步健康`。
2. 加入 **获取健康样本**（每个指标一块，或先做一个指标打通）：
   - HRV / 静息心率 / 步数 / 睡眠 / 活动能量
   - 时间范围：今天（或最近 24 小时）
3. 用 **重复** 或 **字典** 把每条编成：
   - `metric_type`：上表英文名
   - `timestamp`：样本开始时间的 ISO 字符串
   - `value`：数字（健康 Quantity 先「计算 + 0」，不要把 `16 count` 直接塞进 JSON）
   - `source`：`healthkit`
4. 加入 **获取 URL 内容**：
   - 方法 `POST`
   - URL：`http://<Mac-IP>:8788/ingest/healthkit`
   - 请求头：`Content-Type: application/json`，`X-PHA-Ingest-Token: <你的 token>`
   - 请求体：`{"user_id":"default","samples":[...]}`
5. 自动化（可选）：每天晚上跑一次。后台可能漏跑；v1 接受，以库里 `as_of` 为准。

打通判据（在 Mac 上）：

```bash
sqlite3 data/pha_storage.db \
  "SELECT metric_type, timestamp, value, sample_id FROM wearable_data WHERE sample_id LIKE 'healthkit|%' ORDER BY timestamp DESC LIMIT 20;"
sqlite3 data/pha_storage.db \
  "SELECT day, steps, resting_heart_rate_bpm, hrv_rmssd_ms, sleep_hours, active_energy_kcal FROM wearable_daily ORDER BY day DESC LIMIT 5;"
```

`as_of`（日表 `day`）须与健康 App 里看到的**同一天**，数值量级合理（例如 HRV 几十 ms 而不是 0.04）。

手机连不上 Mac 时：先确认 Tailscale 双方在线、Mac 防火墙放行 8788、PHA 已 `PHA_HOST=0.0.0.0` 重启。

---

## 4. 红线

- 不把健康 JSON 发到项目方服务器；只发你自己的 Mac / VPN。
- ingest 失败不补样本、不用 LLM 填数。
- zip 导入仍走原通道。全量 zip **不会删除** `sample_id` 以 `healthkit|` 开头的行；导入后按日重算，步数取各 source 合计的 **max**。
