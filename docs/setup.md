# 接入步骤

## 房间看板

修改 `examples/rooms.json` 的房间与实体；原生详细控制由 HA 集成的能力决定。只有明确配置 `quick_toggle: true` 的 light/switch 才出现图标快捷开关。`protected: true` 禁用快捷切换，但保留原生详情入口，并不是设备权限系统。

生成文件后复制到 HA 的 `config/dashboards/rooms.yaml`，在 `configuration.yaml` 中合并以下配置，不覆盖现有 `lovelace`：

```yaml
lovelace:
  dashboards:
    home-rooms:
      mode: yaml
      title: 房间
      icon: mdi:home
      show_in_sidebar: true
      filename: dashboards/rooms.yaml
```

## 国网

适用 macOS/Linux，有安装好的 Google Chrome。仅上海单户号验证；本工具不自动登录或解验证码。

```bash
python -m pip install -e '.[sgcc]'
mkdir -p .local/sgcc-state
chmod 700 .local/sgcc-state
```

用专用 Chrome profile 启动有头浏览器，CDP 只监听回环地址。例如 macOS：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-address=127.0.0.1 --remote-debugging-port=9227 \
  --user-data-dir="$PWD/.local/sgcc-browser" \
  https://www.95598.cn/osgweb/my95598
```

人工登录并确认户号与账单可见，然后运行：

```bash
ha-local-kit-sgcc --state-dir .local/sgcc-state --ha-dir /path/to/ha-config/sgcc
# 兼容模式：用导出的私有会话采集。
ha-local-kit-sgcc --headless --state-dir .local/sgcc-state --ha-dir /path/to/ha-config/sgcc

# 优先复用上面已登录的专用 Chrome；未运行时用同一配置目录启动无界面 Chrome。
ha-local-kit-sgcc --headless --prefer-browser \
  --profile-dir "$PWD/.local/sgcc-browser" \
  --state-dir "$PWD/.local/sgcc-state" --ha-dir /path/to/ha-config/sgcc
```

`--cdp-url` 可覆盖默认本机 CDP 地址，仍应只连接国网专用浏览器。不要使用个人日常 Chrome 配置目录。复用时会导航现有国网标签页，采集后保持浏览器打开；后备模式关闭自己启动的浏览器。若配置目录已被其他 Chrome 占用，保留 Chrome 的锁并让本次采集失败，不删除锁或强杀进程。

可从系统调度器每天执行一次开始；需要给网站正常续期机会时，可试用每 6 小时一次，例如 02:30、08:30、14:30、20:30。调度器需传入绝对路径。增加正常访问频率不能保证延长服务器最长登录期限；会话失效或安全验证再次出现，仍需人工登录，不做密集失败重试。并发采集有本机文件锁，单次有 240 秒总超时。

采集会重新加载页面核验账户，不能仅凭缓存中的“退出”判断已登录。明确的认证拒绝显示 `login_required`，无法确认账户但没有认证拒绝证据时仍显示 `account_unconfirmed`。已核验账户后保存更新的会话；sessionStorage 只在空标签页初始化，避免导航时覆盖网站刚更新的令牌。看板在失败时标明保留的是上次成功数据。

禁止将 state-dir、profile-dir 放入 HA 的 `www`、公开仓库或任何公开目录。目录里包括 Cookie、IndexedDB、会话令牌和家庭历史，即使不含密码也不是可发布资料。

将 `ha_local_kit/sgcc/snapshot.py` 复制到 HA 的 `/config/sgcc/snapshot.py`。生成原生传感器：

```bash
python scripts/build-sgcc-sensors.py > sensors.yaml
```

复制到 `config/sgcc/sensors.yaml` 后，合并 `command_line: !include sgcc/sensors.yaml`。如果已有 command_line，合并传感器列表；不要重复写 YAML 顶层键。HA 中应产生 `sensor.sgcc_daily`、`sensor.sgcc_status` 等实体；若名称冲突被添加后缀，请在看板配置中同步改名。

获取前端资源并复制到 HA `www/sgcc-ui/`：

```bash
python scripts/fetch-sgcc-ui.py .local/sgcc-ui
ha-local-kit-electricity --dashboard-path electricity-board > electricity.yaml
```

注册模块资源 `/local/sgcc-ui/apexcharts-card.js?v=2.2.3` 与 `/local/sgcc-ui/flex-table-card.js?v=1.4`，类型均为 JavaScript Module。通过 HA 管理界面注册，保留随资源下载的许可证。

将 electricity.yaml 作为独立 YAML dashboard，键名用 `electricity-board`；也可使用 `apply_dashboard(rooms)` 合并到 `home-rooms` 看板。默认使用最近 31 天日用电、按月账单与本年月度电量。没有任何小时用电读数，也没有向 Energy 统计库回填历史。

HA 的源数据读取每 300 秒执行一次本地文件读取，不会每 300 秒访问国网。失败时保留旧值；36 小时未成功后标记过期。私有 SQLite 为历史留档，当前看板读取最新一次成功抓取的日/月数组。

## TCP 转发与 LG

`examples/relays.json` 使用文档保留地址，必须换成自己已确认的目标地址。先验证 HA 直连；仅在需要时运行 `ha-local-kit-relays --config relays.json`。全部监听 `127.0.0.1`，不向公网开放代理。

LG 使用 HA 原生 webOS 集成；连接过程中在电视上接受配对。某些虚拟机网络还需要定向路由/SNAT；本仓库不自动修改防火墙。遥控的次级 WebSocket 地址、待机唤醒与主控制连接应分别验证。

## 3D

按 README 构建，将 `frontend/dist/home-digital-card.js`、`home.glb`、`layout.json` 和 Three.js 许可证复制到 HA `www/digital-home/`。注册 `/local/digital-home/home-digital-card.js?v=0.1.0` 为模块，添加：

```yaml
type: custom:home-digital-card
asset_base: /local/digital-home
version: 0.1.0
```

先替换示例实体，再通过 HA 状态验证绑定。卡片不存 token；使用当前 HA 登录会话。真实户型和布局文件即使不含密码，也属于家庭隐私。
