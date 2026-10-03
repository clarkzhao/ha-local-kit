# LifeSmart 兼容补丁（GPL-3.0）

上游：[MapleEve/lifesmart-for-homeassistant](https://github.com/MapleEve/lifesmart-for-homeassistant)，验证基线 `502e5ac2f5c0f33a3d4b4e92b0d3ea735d32af7e`。

该目录包含匹配上游的片段，按 GPL-3.0 分发，见 `../../licenses/GPL-3.0.txt`；不是核心 MIT 包的一部分。未复制完整上游集成。

补丁覆盖 VRF 控制、聚合状态推送、`SL_LI_WW` 灯带调光调色及 TCP 重连后的状态同步。请用固定基线的独立副本，查看差异，再在与 HA 相同依赖的环境运行隔离回归。脚本不安装集成或重启 HA；单个补丁脚本只应对测试副本执行。

`stage.py` 从原始基线创建新目录，按 VRF → 聚合推送 → 灯带 → 状态同步的顺序应用补丁。输出不能位于源码目录内，也不能已存在；失败后保留副本供排查，重新执行需另选新目录。已有补丁的集成不适合作为这个入口的输入。

```bash
python extras/lifesmart/stage.py /path/to/upstream/lifesmart /path/to/staged/lifesmart
diff -ru /path/to/upstream/lifesmart /path/to/staged/lifesmart

# 在带 Home Assistant 和上游依赖的解释器中执行。
python extras/lifesmart/regression.py /path/to/staged/lifesmart
python extras/lifesmart/light_regression.py /path/to/staged/lifesmart
python extras/lifesmart/refresh_regression.py /path/to/staged/lifesmart
```

回归需要上游依赖及 Home Assistant，不属于轻量核心 CI。命令方法均被 mock，不控制设备。上游合并等价修复后应停止使用对应补丁。该仓库的公开不意味着补丁已向上游提交或被合并。

## 灯带控制与状态同步

`patch-light.py` 将 `SL_LI_WW` 改为逐通道写入 P1（亮度）和 P2（色温），避免已观察到的多 IO 请求被网关拒绝。只写请求的通道，修正 P2 的方向（0 暖、255 冷），由设备推送确认界面状态，并将命令失败反馈给 HA。色温范围仍沿用上游的 2700–6500 K，未做物理光谱校准。此补丁依赖 `patch-updates.py` 的聚合推送代码。

`patch-refresh.py` 在登录、重连及后续 GetConfig 响应后发布设备快照，先同步 Hub 和 HA 共享缓存，再通知实体。定期刷新执行真实的只读查询，避免灯带已经开启而 HA 长时间保留旧的关闭状态。

两项补丁先准备所有目标，再统一检查语法后写入，避免第二个目标不匹配时只写入第一份文件；保留各文件的换行格式。`patch_utils.py` 必须与补丁放在同一目录。写入失败仍可能留下不完整的测试副本，因此这不是生产安装器。

在 HA 2026.9.1 环境通过 9 项灯带、6 项状态同步及 12 项 VRF 回归；TCP 读写、重连和实体通知采用隔离对象与 mock 传输。一个私有 `SL_LI_WW_V4` 实例另有调光调色及只读重连验证，不代表所有型号或固件都兼容。默认 CI 的 `tests/test_lifesmart_patches.py` 检查失败不部分写入、换行保留、输出目录限制及原始副本不被修改，不依赖 HA。

## 本地长连接阻塞启动

在上述基线中，`hub.py` 使用 `hass.async_create_task` 创建持续运行的 TCP 连接任务。该任务可能被 HA 启动等待机制当作需要完成的工作，导致设备已经连接而启动仍在等待。`startup_patch.py` 将其改为配置条目管理的 `async_create_background_task`，保留原有取消与清理逻辑。

这项修复此前在 HA 2026.9.1 的一个本地部署验证；其他 HA 版本需要确认 `ConfigEntry.async_create_background_task(hass, target, name)` 可用，不能直接推广到所有旧版。它可以与前面的 VRF 和状态更新补丁分别使用。

```bash
# 源文件只读：检查并生成一个独立的新文件。
python extras/lifesmart/startup_patch.py /path/to/staged/lifesmart --check
python extras/lifesmart/startup_patch.py /path/to/staged/lifesmart \
  --output /path/to/staged/hub.startup-patched.py

# 人工审查差异后，仅在独立测试副本内替换。
diff -u /path/to/staged/lifesmart/hub.py /path/to/staged/hub.startup-patched.py
cp /path/to/staged/hub.startup-patched.py /path/to/staged/lifesmart/hub.py

# 使用带 Home Assistant 和上游依赖的测试解释器；TCP 客户端被替换为 mock。
python extras/lifesmart/startup_regression.py /path/to/staged/lifesmart
```

脚本只接受一个已知匹配块；不匹配则退出且不写文件。源文件始终只读，生成结果保留换行，新文件按 POSIX `600` 创建；已有输出拒绝覆盖。如果源文件已经包含补丁则不产生输出。这样，即使编辑器并发修改源文件，工具也不会把编辑覆盖掉。输出代表读取时的源文件快照，人工采用前应再次比较当前源文件。写入异常可能留下不完整的新输出，应检查后删除再重试。

它不验证整个上游目录的版本，因此仍应使用标注的固定基线、审查 diff 并执行回归；它也不能自动判断一个路径是否是你的生产目录。上面的 `cp` 是用户审查后在独立测试副本中执行的步骤，工具不替你安装或重启 HA。

默认 CI 的 `tests/test_lifesmart_startup.py` 使用合成生命周期夹具验证启动不会等待永久连接、卸载取消任务、失败不改文件和重复应用。`startup_regression.py` 则验证真实上游 Hub 的方法与 HA 方法签名；不是完整 HA 启动端到端测试。
