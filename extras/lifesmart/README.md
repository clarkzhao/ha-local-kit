# LifeSmart VRF 兼容补丁（GPL-3.0）

上游：[MapleEve/lifesmart-for-homeassistant](https://github.com/MapleEve/lifesmart-for-homeassistant)，验证基线 `502e5ac2f5c0f33a3d4b4e92b0d3ea735d32af7e`。

该目录包含匹配上游的片段，按 GPL-3.0 分发，见 `../../licenses/GPL-3.0.txt`；不是核心 MIT 包的一部分。未复制完整上游集成。

请先在独立副本应用两个补丁，查看差异，再在与 HA 相同依赖的环境运行隔离回归。不要直接对正在运行的 HA 目录打补丁。脚本检测匹配块，但不是事务式安装器；失败后丢弃测试副本重新开始。

```bash
python extras/lifesmart/patch-vrf.py /path/to/staged/lifesmart
python extras/lifesmart/patch-updates.py /path/to/staged/lifesmart
python extras/lifesmart/regression.py /path/to/staged/lifesmart
```

回归需要上游依赖及 Home Assistant，不属于轻量核心 CI。命令方法均被 mock，不控制设备。上游合并等价修复后应停止使用对应补丁。该仓库的公开不意味着补丁已向上游提交或被合并。

## 本地长连接阻塞启动

在上述基线中，`hub.py` 使用 `hass.async_create_task` 创建持续运行的 TCP 连接任务。该任务可能被 HA 启动等待机制当作需要完成的工作，导致设备已经连接而启动仍在等待。`startup_patch.py` 将其改为配置条目管理的 `async_create_background_task`，保留原有取消与清理逻辑。

这项修复此前在 HA 2026.9.1 的一个本地部署验证；其他 HA 版本需要确认 `ConfigEntry.async_create_background_task(hass, target, name)` 可用，不能直接推广到所有旧版。它可以与前面的 VRF 和状态更新补丁分别使用。

```bash
# 在独立副本中检查、应用。两个步骤均不会重启 HA。
python extras/lifesmart/startup_patch.py /path/to/staged/lifesmart --check
python extras/lifesmart/startup_patch.py /path/to/staged/lifesmart

# 使用带 Home Assistant 和上游依赖的测试解释器；TCP 客户端被替换为 mock。
python extras/lifesmart/startup_regression.py /path/to/staged/lifesmart
```

脚本只接受一个已知匹配块；不匹配则退出且不写文件。重复运行是无操作，保留换行和文件权限，并在同目录通过临时文件替换。它不验证整个上游目录的版本，因此仍应使用标注的固定基线、审查 diff 并执行回归；它也不能自动判断一个路径是否是你的生产目录。

默认 CI 的 `tests/test_lifesmart_startup.py` 使用合成生命周期夹具验证启动不会等待永久连接、卸载取消任务、失败不改文件和重复应用。`startup_regression.py` 则验证真实上游 Hub 的方法与 HA 方法签名；不是完整 HA 启动端到端测试。
