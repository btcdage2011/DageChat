# DageChat: Nostr 协议 Python 实现研究

**DageChat** 是一个基于 **Nostr (Notes and Other Stuff Transmitted by Relays)** 协议的开源客户端实现参考。

本项目旨在从代码层面研究去中心化架构下的数据传输机制、验证 **NIP-44 (XChaCha20-Poly1305)** 加密算法在群组通讯中的应用可行性，以及 **NIP-59 (Gift Wrap)** 封装协议的技术实现细节。

> **⚠️ 注意**：本项目仅供计算机网络技术研究、密码学学习及协议测试使用。不提供任何编译好的可执行文件（EXE），仅提供源代码供开发者交流。

## 🛠 技术特性

本项目主要涵盖以下技术点的代码实现与验证：

*   **去中心化网络协议 (NIP-01)**
    *   实现了标准的 WebSocket 客户端连接池 (`AsyncRelayManager`)。
    *   支持多 Relay 节点的并发订阅、发布与状态管理。
    *   实现了 Event ID 的生成与 Schnorr 签名 (BIP-340) 流程。

*   **端到端加密研究 (NIP-44 v2)**
    *   集成了 `secp256k1` 椭圆曲线算法。
    *   验证了 **XChaCha20-Poly1305** 算法在即时通讯场景下的性能表现。
    *   实现了基于共享密钥的群组加密通信逻辑。

*   **协议封装与路由 (NIP-59)**
    *   实现了 **Gift Wrap** 机制：通过生成临时密钥对消息进行多层封装（Rumor -> Seal -> Wrap）。
    *   验证了在无元数据泄露前提下的消息路由投递技术。

*   **经济防御机制 (NIP-13)**
    *   内置分级 **工作量证明 (PoW)** 挖矿模块。
    *   验证了通过算力门槛遏制垃圾消息（Spam）的技术方案。

## 📂 项目结构

*   `gui.py`: 基于 `CustomTkinter` 的图形界面入口，演示了异步消息的 UI 渲染逻辑。
*   `client_persistent.py`: 核心客户端逻辑，负责网络 IO 和事件分发。
*   `nostr_crypto.py`: 加密原语封装，包含 NIP-44 和 BIP-340 的具体实现。
*   `db.py`: 本地 SQLite 存储实现。
*   `dagechat-relay-*.py`: 两个简易的中继器实现（分别基于 Redis 和 SQLite），用于本地闭环测试。

## 🚀 运行指南

本项目仅支持源码运行，需要具备 Python 开发环境。

### 1. 环境准备

请确保已安装 Python 3.9+。

```bash
# 克隆项目
git clone https://github.com/btcdage2011/DageChat.git
cd dagechat

# 创建虚拟环境 (推荐)
python -m venv venv
# Windows 激活
venv\Scripts\activate
# Linux/Mac 激活
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```
### 3. 启动客户端

```bash
python gui.py
```

### 4. 数据存储路径

如果在程序根目录下创建 `setup.ini` 文件，可指定本地数据库的存储位置（便于将数据存放在加密盘或移动介质中）：

```ini
[Setup]
DbPath=D:\MySecureData
```

## ⚖️ 免责声明 (Disclaimer)

在使用本项目代码前，请务必仔细阅读以下条款：

1.  **技术研究用途**：本软件及源代码仅供计算机网络技术研究、密码学学习及协议测试使用。
2.  **无中心化运营**：本项目是一个纯粹的客户端协议实现，**不提供、不运营、不维护**任何中心化的服务器或中继节点（Relay）。所有数据传输均依赖于用户自行配置的第三方网络。
3.  **合规使用义务**：严禁使用本软件从事任何违反当地法律法规的活动（包括但不限于诈骗、赌博、色情、洗钱、政治敏感信息传播等）。
4.  **免责条款**：由于本软件的去中心化特性，开发者无法控制、审核或删除通过网络传输的任何内容。**因用户违规使用产生的一切法律责任，概由用户自行承担，与开源代码贡献者无关。**

---

**Author**: @BTCDage (技术交流)
**License**: MIT (仅限技术研究)


