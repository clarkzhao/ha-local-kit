# 云鲸中国区身份准备（实验性）

```bash
python extras/narwal/account_helper.py --state-dir .local/narwal
```

打开终端显示的 `http://127.0.0.1:8766`。用已有账号手机号与短信验证码人工登录，读取配置本地集成所需的 Device ID / product key。此入口不是 HA 集成，也不执行清扫命令。

账号 token 仅在内存中短暂保留，成功查询后清除；Device ID 是私有设备标识，写到指定私有目录。公开版移除了 SN 输出字段。文件目录必须位于公开仓库/静态站点之外；Windows 使用账户目录 ACL，POSIX 使用受限权限。

首次配置仍需要云账号；之后本地运行方式由选择的 Narwal HA 集成决定。接口来自 App/H5 行为研究，可能改变。遇到验证码、安全验证或账号限制时按 App 官方流程处理，不自动绕过。不要将此服务代理至公网。

参考集成及许可证来源见仓库 `THIRD_PARTY_NOTICES.md`。
