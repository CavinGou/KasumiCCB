# KasumiCCB 🎸

> 提取自 kasumi 的娶群友功能 — BanG Dream! 风格卡片渲染插件

基于 [AstrBot](https://github.com/AstrBot) 框架的 QQ 群娱乐插件，随机抽取群成员并生成 **BanG Dream!** 风格娶群友卡片。

## ✨ 功能

- 🎰 **娶群友** — 随机抽取一位群成员，生成 BanG Dream! 风格卡牌
- 🎴 **精美渲染** — 自动下载头像，合成精美角色卡片
- ⚡ **多 NapCat 实例** — 支持多个 NapCat 连接地址，自动负载均衡

## 📦 安装

1. 将本插件放入 AstrBot 的 `addons/` 目录下
2. 重启 AstrBot 即可（依赖会自动安装）

## ⚙️ 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `napcat_host` | NapCat 连接地址（支持多个，逗号分隔） | `127.0.0.1:3000` |
| `napcat_token` | NapCat API Token | 空 |
| `request_timeout` | 请求超时时间（秒） | `10` |

## 🎮 命令

| 命令 | 说明 |
|------|------|
| `娶群友` / `qqy` / `ccb` | 随机抽取群成员并生成卡片 |

## 📸 效果

发送 `娶群友` 后，机器人会：
1. 随机选择一位群成员（排除自己和机器人）
2. 下载其 QQ 头像
3. 生成 BanG Dream! 风格角色卡片
4. 发送卡片图片 + 配文

## 📄 许可

本项目基于 [MIT](LICENSE) 协议开源。

## 🙏 致谢

- 原项目：[Kasumi-Games/kasumi-next](https://github.com/Kasumi-Games/kasumi-next)
- 框架：[AstrBot](https://github.com/AstrBot)
