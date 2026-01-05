# DageChat: Nostr Protocol Implementation Research
# DageChat: Nostr 协议 Python 实现研究

**DageChat** is an open-source client implementation reference based on the **Nostr (Notes and Other Stuff Transmitted by Relays)** protocol.
**DageChat** 是一个基于 **Nostr (Notes and Other Stuff Transmitted by Relays)** 协议的开源客户端实现参考。

This project aims to research data transmission mechanisms within a decentralized architecture from a code perspective, verify the feasibility of the **NIP-44 (XChaCha20-Poly1305)** encryption algorithm in group communications, and explore the technical implementation details of the **NIP-59 (Gift Wrap)** encapsulation protocol.
本项目旨在从代码层面研究去中心化架构下的数据传输机制、验证 **NIP-44 (XChaCha20-Poly1305)** 加密算法在群组通讯中的应用可行性，以及 **NIP-59 (Gift Wrap)** 封装协议的技术实现细节。

> **⚠️ Note / 注意**：
>
> This project is strictly for computer network technology research, cryptography study, and protocol testing purposes. **No compiled executables (EXE) are provided**; only source code is available for developer exchange.
>
> 本项目仅供计算机网络技术研究、密码学学习及协议测试使用。**不提供任何编译好的可执行文件（EXE）**，仅提供源代码供开发者交流。

---

## 🛠 Technical Features / 技术特性

This project covers the code implementation and verification of the following key technical points:
本项目主要涵盖以下技术点的代码实现与验证：

*   **Decentralized Network Protocol (NIP-01) / 去中心化网络协议**
    *   Implemented a standard WebSocket client connection pool (`AsyncRelayManager`).
    *   Supports concurrent subscription, publishing, and status management for multiple Relay nodes.
    *   Implemented Event ID generation and the Schnorr signature (BIP-340) process.
    *   实现了标准的 WebSocket 客户端连接池 (`AsyncRelayManager`)。
    *   支持多 Relay 节点的并发订阅、发布与状态管理。
    *   实现了 Event ID 的生成与 Schnorr 签名 (BIP-340) 流程。

*   **End-to-End Encryption Research (NIP-44 v2) / 端到端加密研究**
    *   Integrated the `secp256k1` elliptic curve algorithm.
    *   Verified the performance of the **XChaCha20-Poly1305** algorithm in instant messaging scenarios.
    *   Implemented group encryption communication logic based on shared keys.
    *   集成了 `secp256k1` 椭圆曲线算法。
    *   验证了 **XChaCha20-Poly1305** 算法在即时通讯场景下的性能表现。
    *   实现了基于共享密钥的群组加密通信逻辑。

*   **Protocol Encapsulation & Routing (NIP-59) / 协议封装与路由**
    *   Implemented the **Gift Wrap** mechanism: Multi-layer message encapsulation using temporary keys (Rumor -> Seal -> Wrap).
    *   Verified message routing and delivery techniques without leaking metadata.
    *   实现了 **Gift Wrap** 机制：通过生成临时密钥对消息进行多层封装（Rumor -> Seal -> Wrap）。
    *   验证了在无元数据泄露前提下的消息路由投递技术。

*   **Economic Defense Mechanism (NIP-13) / 经济防御机制**
    *   Built-in tiered **Proof of Work (PoW)** mining module.
    *   Verified technical solutions for curbing spam messages through computational power thresholds.
    *   内置分级 **工作量证明 (PoW)** 挖矿模块。
    *   验证了通过算力门槛遏制垃圾消息（Spam）的技术方案。

---

## 📂 Project Structure / 项目结构

*   `gui.py`: Graphical interface entry based on `CustomTkinter`, demonstrating UI rendering logic for asynchronous messages. (基于 `CustomTkinter` 的图形界面入口)
*   `client_persistent.py`: Core client logic responsible for network IO and event dispatching. (核心客户端逻辑)
*   `nostr_crypto.py`: Cryptographic primitive encapsulation, including concrete implementations of NIP-44 and BIP-340. (加密原语封装)
*   `db.py`: Local SQLite storage implementation. (本地 SQLite 存储实现)
*   `dagechat-relay-*.py`: Two simple relay implementations (based on Redis and SQLite respectively) for local closed-loop testing. (简易中继器实现)

---

## 🚀 Running Guide / 运行指南

This project only supports running from source code and requires a Python development environment.
本项目仅支持源码运行，需要具备 Python 开发环境。

### 1. Prerequisites / 环境准备

Please ensure Python 3.9+ is installed.
请确保已安装 Python 3.9+。

```bash
# Clone the project / 克隆项目
git clone https://github.com/btcdage2011/DageChat.git
cd dagechat

# Create virtual environment (Recommended) / 创建虚拟环境 (推荐)
python -m venv venv

# Activate on Windows / Windows 激活
venv\Scripts\activate

# Activate on Linux/Mac / Linux/Mac 激活
source venv/bin/activate
```

### 2. Install Dependencies / 安装依赖

```bash
pip install -r requirements.txt
```

### 3. Launch Client / 启动客户端

```bash
python gui.py
```

### 4. Data Storage Path / 数据存储路径

You can specify a custom storage location for the local database by creating a `setup.ini` file in the program's root directory (useful for storing data on encrypted drives or removable media).
如果在程序根目录下创建 `setup.ini` 文件，可指定本地数据库的存储位置（便于将数据存放在加密盘或移动介质中）：

```ini
[Setup]
DbPath=D:\MySecureData
```

---

## ⚖️ Disclaimer / 免责声明

Before using the code in this project, please read the following terms carefully:
在使用本项目代码前，请务必仔细阅读以下条款：

1.  **Research Purpose Only**: This software and source code are strictly for computer network technology research, cryptography study, and protocol testing.
    **技术研究用途**：本软件及源代码仅供计算机网络技术研究、密码学学习及协议测试使用。

2.  **No Centralized Operation**: This project is a pure client-side protocol implementation. It **does not provide, operate, or maintain** any centralized servers or Relay nodes. All data transmission relies on third-party networks configured by the user.
    **无中心化运营**：本项目是一个纯粹的客户端协议实现，**不提供、不运营、不维护**任何中心化的服务器或中继节点（Relay）。所有数据传输均依赖于用户自行配置的第三方网络。

3.  **Compliance Obligation**: It is strictly prohibited to use this software for any activities that violate local laws and regulations (including but not limited to fraud, gambling, pornography, money laundering, spreading politically sensitive information, etc.).
    **合规使用义务**：严禁使用本软件从事任何违反当地法律法规的活动（包括但不限于诈骗、赌博、色情、洗钱、政治敏感信息传播等）。

4.  **Limitation of Liability**: Due to the decentralized nature of this software, the developer cannot control, audit, or delete any content transmitted over the network. **Any legal liability arising from user misuse shall be borne solely by the user and is unrelated to the open-source contributors.**
    **免责条款**：由于本软件的去中心化特性，开发者无法控制、审核或删除通过网络传输的任何内容。**因用户违规使用产生的一切法律责任，概由用户自行承担，与开源代码贡献者无关。**

---

**Author**: @BTCDage (Technical Exchange / 技术交流)
**License**: MIT (Research Use Only / 仅限技术研究)
