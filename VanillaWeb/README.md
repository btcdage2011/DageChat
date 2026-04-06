# DageChat - VanillaWeb Client 🍦

![Nostr](https://img.shields.io/badge/Protocol-Nostr-purple.svg)
![Vanilla JS](https://img.shields.io/badge/Tech-Vanilla%20JS-yellow.svg)
![Zero Build](https://img.shields.io/badge/Build-Zero%20Config-success.svg)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

> **极简、硬核、高强度的去中心化加密通讯终端。**
> A zero-build, ultra-secure, cypherpunk-style Nostr chat client.

## 💡 为什么是 VanillaWeb？(Why Vanilla?)

本客户端采用 **纯原生 HTML + JavaScript (Vanilla JS)** 编写，**零构建工具** (没有 npm, 无需 Webpack/Vite，没有 React/Vue 依赖)。

在追求极致隐私与安全的 Web3 / Nostr 生态中，代码的“可审计性”至关重要。单文件/免编译的架构确保了：
1. **绝对透明**：所见即所得，任何人都可以用记事本打开并审计核心加密逻辑，杜绝软件供应链投毒。
2. **开箱即用**：无需任何开发环境配置，下载源码后**双击 HTML 文件**即可在浏览器中运行，甚至可以离线放入 U 盘随身携带。
3. **极易部署**：可以直接托管在 GitHub Pages、IPFS 或任何静态服务器上。

## 🛡️ 核心特性 (Core Features)

### 1. 军事级密码学与协议支持
*   **NIP-44 深度重构与兼容**：内置完美适配 Python 后端的 NIP-44 加密引擎。修复了底层 ECDH 曲线推导过程中的 Y 坐标奇偶性雪崩问题，确保 100% 的跨语言端到端加密兼容。
*   **NIP-59 (Gift Wrap) 绝对匿名**：支持协议级的元数据混淆（Rumor -> Seal -> Wrap），不仅隐藏聊天内容，更隐藏通讯双方的社交关系网。
*   **本地 AES-GCM 强加密**：私钥永不触网。在本地持久化时，强制要求用户设置密码，并使用 WebCrypto AES-GCM 算法进行高强度加密。支持闲置超时自动锁屏（防窥屏）。

### 2. 独创的抗隐写术与安全防御
*   **Canvas 物理级图像脱敏引擎**：在发送图片前，前端强制使用 Canvas 引擎注入纯白背景并重新导出为 JPEG。从物理层面彻底摧毁 Alpha 透明通道隐藏恶意代码（隐写术）的可能，并强力剥离所有 EXIF 等地理位置元数据。

### 3. 高阶去中心化通讯体验
*   **多节点并发广播 (Relay Pool)**：支持自定义 WebSocket 节点，多路复用防洪防丢信。
*   **客户端 PoW 防洪 (NIP-13)**：发送群组消息时内置非阻塞式的工作量证明（PoW）挖矿机制，保护网络免受垃圾信息干扰。
*   **“幽灵”共享群组**：创新性的共享私钥群聊模式。群成员共用一把私钥收发 NIP-59 信件，实现身份无法追踪的“暗网级”群聊体验。
*   **Kind 3 加密云端漫游**：通讯录、群组、节点列表及黑名单，全部打包重加密后云端同步，多设备无缝漫游。

### 4. 流畅的原生 UI 交互
*   支持单文件内的**暗黑/明亮模式**实时切换。
*   支持消息合并转发、逐条转发、长按菜单、@成员提醒。
*   支持原生 JavaScript 递归解析生成的**聊天记录套娃导出（HTML/TXT）**。
*   利用底层防抖（Debounce）结合 DOM 末尾截断渲染，保障超长会话和图片流的秒级丝滑加载。

## 🚀 快速开始 (Quick Start)

**方法一：本地双击运行（推荐）**
1. 克隆或下载本仓库代码。
2. 进入 `VanillaWeb` 文件夹。
3. 使用浏览器（推荐 Chrome/Edge/Safari）直接打开 `index.html`。
4. 导入你的 `nsec` 私钥，设置本地保护密码，即可开始聊天！

**方法二：部署到静态服务器**
直接将本文件夹推送到 GitHub Pages、Vercel、Netlify 或任何 Nginx 服务器的根目录下，无需任何 `build` 编译步骤。
