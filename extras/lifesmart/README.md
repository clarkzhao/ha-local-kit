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
