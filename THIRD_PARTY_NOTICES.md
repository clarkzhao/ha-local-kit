# 来源与许可证

- 核心 Python、房间生成、3D 卡片和合成演示：本项目，MIT。
- `extras/lifesmart/`：对 [MapleEve/lifesmart-for-homeassistant](https://github.com/MapleEve/lifesmart-for-homeassistant) 的兼容补丁；包含匹配上游的代码片段，按 GPL-3.0 分发。许可证见 `licenses/GPL-3.0.txt`。上游完整驱动未复制到本仓库，也不打包进 MIT Python wheel。
- Three.js 0.180.0：MIT；通过 npm 获取，构建产物保留 `THREE-LICENSE.txt`。
- esbuild 0.25.10：MIT，构建依赖。
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card) v2.2.3：上游发布模块及其许可证由下载脚本获取；发布模块内含的依赖保留原始声明，不按本项目 MIT 重新授权。
- [Flex Table Card](https://github.com/custom-cards/flex-table-card) v1.4：MIT，固定提交与 SHA-256 见 `examples/ui-assets.json`。
- Playwright：Apache-2.0，通过可选依赖安装；Google Chrome 是用户独立安装的浏览器，不随本项目分发。
- [ARC-MX/sgcc_electricity_new](https://github.com/ARC-MX/sgcc_electricity_new)：国网字段发现与初期调研参考，Apache-2.0。本公开版本自行维护限定字段读取与规范化代码，不导入、复制打包上游脚本。
- [sjmotew/NarwalIntegration](https://github.com/sjmotew/NarwalIntegration)、[rudyll/narwal_r](https://github.com/rudyll/narwal_r)、[nadavbau/narwal-integration](https://github.com/nadavbau/narwal-integration)：云鲸集成路径、设备字段和认证头参考。未分发其驱动。
- 云鲸短信辅助的端点和字段来自官方 App/H5 行为研究，不是官方授权的公开 API 承诺；没有打包官方 App、网站脚本、签名密钥或账号数据。
- Home Assistant 原生 LG webOS 集成继续由 HA 提供；本项目没有另行实现 LG 协议。

`licenses/` 中第三方许可文本不改变核心 MIT 与 LifeSmart extras GPL 的目录边界。商标属于各自权利人；本项目不代表厂商或 Home Assistant 官方。
