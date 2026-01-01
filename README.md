# DageChat Relay (中继器)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green)](https://www.python.org/)

**DageChat 去中心化通信架构的官方中继器（Relay）实现。**

DageChat 是一个基于主权治理与元数据混淆的去中心化通信网络。本项目（DageChat-Relay）是该网络的基础设施节点，负责加密数据的临时存储与路由。

> ⚠️ **注意**：本项目仅包含服务端 Relay 代码。DageChat 客户端 (Client) 目前处于内部灰度测试阶段，将于近期开源。

---

## 🌟 版本说明

为了适应从个人极客到公共服务商的不同需求，我们提供了两个版本的实现：

### 1. 轻量版 (SQLite)
*   **文件**: `dagechat-relay-sqlite.py`
*   **特点**: 零依赖（仅需 Python 标准库 + aiosqlite），单文件部署。
*   **适用场景**: 个人私有节点、家庭服务器（树莓派/NAS）、小型群组。
*   **数据存储**: 本地 `.db` 文件，易于备份和迁移。

### 2. 高性能版 (Redis)
*   **文件**: `dagechat-relay-redis.py`
*   **特点**: 全内存操作，极高的读写吞吐量 (TPS)。
*   **适用场景**: 公共大厅、高并发服务节点、千人级群组。
*   **数据存储**: 依赖 Redis 服务，支持数据自动过期 (TTL)。

---

## 🛡️ 核心特性

*   **哑中继设计 (Dumb Relay)**: 服务器端**不解密**内容，**不存储**用户关系图谱。
*   **抗审查**: 严格遵循 [NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md) 协议标准。
*   **反垃圾机制**: 内置 [NIP-13](https://github.com/nostr-protocol/nips/blob/master/13.md) 工作量证明 (PoW) 校验逻辑。
*   **隐私保护**: 无需手机号注册，无账户体系，仅基于公钥签名验证。

---

## 🚀 快速开始

### 第一步：安装依赖

请确保您的环境中已安装 Python 3.9 或更高版本。

```bash
pip install -r requirements.txt
```

*(`requirements.txt` 需包含: `fastapi`, `uvicorn`, `aiosqlite`, `redis`, `websockets`)*

### 第二步：配置 (可选)

项目根目录下的 `dagechat-relay.json` 是配置文件。您可以修改监听端口、数据库路径或 Redis 连接信息。默认配置即可直接运行。

```json
{
    "server": {
        "host": "0.0.0.0",
        "port": 3008,
        "name": "DageChat Relay"
    },
    "sqlite": {
        "db_file": "relay.db"
    },
    "limits": {
        "max_message_size": 2097152,
        "rate_limit_window": 60,
        "rate_limit_count": 200,
        "data_ttl": 2592000
    }
}
```

### 第三步：启动服务

#### 启动 SQLite 版 (推荐新手)
```bash
python dagechat-relay-sqlite.py
```
终端显示 `🚀 SQLite Relay (Standard) Starting...` 即表示启动成功。

#### 启动 Redis 版
请确保本地 Redis 服务已运行 (`localhost:6379`)。
```bash
python dagechat-relay-redis.py
```

---

## 📚 文档与资源

虽然客户端尚未开源，但您可以通过以下文档深入了解 DageChat 的设计哲学与加密架构：

*   📄 **[技术白皮书 (Whitepaper)](docs/Whitepaper_CN.md)**: 详解 XChaCha20 加密、幽灵群协议与双模治理架构。
*   📖 **[终极百科全书 (Encyclopedia)](docs/Encyclopedia_CN.md)**: 常见问题解答与深度技术剖析。

---

## 🤝 贡献与协议

本项目采用 **GNU AGPL v3** 开源协议。
如果您运行基于此代码的公共服务，您必须向用户公开您的源代码。

*Created by @BTCDage*
