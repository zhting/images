<div align="center">

# 📷 Deep Photo

**隐私优先的本地 AI 照片管理与语义搜索引擎**

用自然语言搜索你的照片 · 全部本地运行 · 无需上传云端

[![CI](https://github.com/zhting/images/actions/workflows/test.yml/badge.svg)](https://github.com/zhting/images/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg)](https://www.python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org)

</div>

---

## ✨ 功能亮点

| 功能 | 说明 |
|:-----|:-----|
| 🔍 **语义搜索** | 用自然语言描述照片内容即可搜索，如"猫在沙发上睡觉"、"海边的日落" |
| 🕐 **智能时光轴** | 按时间线浏览所有照片，自动识别连拍并推荐最佳照片 |
| 👤 **人物识别** | AI 自动检测人脸、聚类分组，按人物浏览照片 |
| 🗺️ **地图视图** | 在交互式地图上可视化你的拍照足迹 |
| 📅 **历史上的今天** | 重温往年今日的珍贵回忆 |
| 🏷️ **智能标签** | 自动识别照片内容并生成分类标签 |
| 🐘 **旅行小象** | AI 生成旅行明信片，让可爱的小象出现在你的照片里 |
| 🔒 **隐私保护** | 文件夹加密锁定，所有处理完全本地化，数据绝不离开你的设备 |
| 🗑️ **智能回收站** | 安全的软删除机制，支持照片恢复 |

## 📸 系统截图

> 使用 `start.bat` 一键启动后，打开浏览器访问 `http://localhost:5173`

## 🏗️ 技术架构

```
┌─────────────────────────────────┐
│     前端 (Vue 3 + TailwindCSS)    │
│  时光轴 │ 搜索 │ 地点 │ 人物 │ 设置  │
└───────────────┬─────────────────┘
                │ REST API
┌───────────────┴─────────────────┐
│       后端 (FastAPI + Python)      │
│                                    │
│  ┌──────────┐  ┌──────────────┐  │
│  │ 路由模块  │  │  核心处理器   │  │
│  │ search   │  │  VisionModel │  │
│  │ timeline │  │  FaceProc    │  │
│  │ organize │  │  LocationProc│  │
│  │ people   │  │  TagGenerator│  │
│  │ travel   │  │  SyncManager │  │
│  │ ...      │  │              │  │
│  └──────────┘  └──────┬───────┘  │
│                        │          │
│  ┌─────────────────────┴───────┐ │
│  │         数据存储层           │ │
│  │  ChromaDB (向量) │ SQLite   │ │
│  └─────────────────────────────┘ │
└──────────────────────────────────┘
```

## 🧠 AI 模型

本项目使用三大开源 AI 模型，全部在本地运行：

### 视觉语义理解 — Google SigLIP
- **模型**: [SigLIP SO400M-patch14-384](https://huggingface.co/google/siglip-so400m-patch14-384)
- **作用**: 核心搜索引擎。将图片和文本映射到同一向量空间，实现"以文搜图"和"以图搜图"
- **体积**: ~1.3 GB

### 智能翻译 — Qwen2.5
- **模型**: [Qwen2.5-0.5B](https://huggingface.co/Qwen) (本地轻量) / 7B (按需加载)
- **作用**: 自动翻译中文搜索词为英文以匹配视觉模型，翻译地理位置名称
- **特点**: 0.5B 版本可在 CPU 上流畅运行

### 人脸识别 — InsightFace
- **模型**: [buffalo_l](https://github.com/deepinsight/insightface)
- **作用**: 人脸检测 → 特征提取 → DBSCAN 聚类，自动按人物分组照片
- **精度**: 基于 ArcFace 的 SOTA 人脸识别精度

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- 约 3GB 磁盘空间（用于 AI 模型首次下载）

### 一键启动

```bash
# 克隆项目
git clone https://github.com/zhting/images.git
cd images

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd web && npm install && cd ..

# 启动（Windows）
start.bat

# 或手动启动
# 后端: python -m src.api.server  (端口 8001)
# 前端: cd web && npm run dev     (端口 5173)
```

启动后打开 `http://localhost:5173`，在设置页面添加照片目录即可开始索引。

## 📂 项目结构

```
├── src/
│   ├── api/                    # FastAPI 后端
│   │   ├── server.py           # 应用入口 (~90行)
│   │   ├── state.py            # 全局状态 & 懒初始化
│   │   ├── models.py           # Pydantic 数据模型
│   │   ├── helpers.py          # 公共工具函数
│   │   └── routes/             # 路由模块 (10个)
│   │       ├── search.py       # 文本/图片/AI 搜索
│   │       ├── timeline.py     # 时光轴 + 连拍检测
│   │       ├── files.py        # 文件浏览 & 缩略图
│   │       ├── organize.py     # 地点/标签/精选/文档
│   │       ├── people.py       # 人脸识别 & 聚类
│   │       ├── privacy.py      # 密码 & 文件夹锁
│   │       ├── config.py       # 配置管理
│   │       ├── system.py       # 索引 & 系统管理
│   │       ├── travel.py       # 旅行小象明信片
│   │       └── trash.py        # 回收站
│   ├── core/                   # 核心业务逻辑
│   │   ├── models.py           # VisionModel (SigLIP)
│   │   ├── sync.py             # 文件扫描 & 同步管理
│   │   ├── face_processor.py   # 人脸处理 (InsightFace)
│   │   ├── location_processor.py # 地理位置解析
│   │   ├── tag_generator.py    # 智能标签生成
│   │   └── translator.py       # 离线翻译 (Qwen2.5)
│   └── database/               # 数据存储层
│       ├── vector_db.py        # ChromaDB 向量数据库
│       └── sqlite_store.py     # SQLite 元数据存储
├── web/                        # Vue 3 前端
│   └── src/
│       ├── views/              # 页面组件
│       └── components/         # 复用组件
├── tests/                      # 自动化测试
├── .github/workflows/          # CI/CD 流水线
├── start.bat                   # 一键启动脚本
└── requirements.txt            # Python 依赖
```

## 🧪 开发 & 测试

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
PYTHONPATH=src python -m pytest tests/ -v

# Windows PowerShell
$env:PYTHONPATH="src"; python -m pytest tests/ -v
```

## ⚙️ CI/CD

本项目使用 GitHub Actions 实现自动化：

| 工作流 | 触发条件 | 内容 |
|:-------|:---------|:-----|
| **CI 测试** | Push / PR → `main` | Python 单元测试 + 前端构建验证 |
| **发布** | Push tag `v*` | 自动构建前端 → 创建 GitHub Release |

## 🔧 技术栈

| 层 | 技术 |
|:--|:-----|
| **前端** | Vue 3 (Composition API), Vue Router, TailwindCSS, Vite, Axios |
| **后端** | FastAPI, Uvicorn, Python 3.10+ |
| **向量数据库** | ChromaDB (语义嵌入存储与检索) |
| **元数据存储** | SQLite (文件路径、时间戳、人脸数据、配置) |
| **视觉模型** | Google SigLIP SO400M |
| **翻译模型** | Qwen2.5-0.5B / 7B |
| **人脸识别** | InsightFace buffalo_l (ArcFace) |
| **测试** | pytest, FastAPI TestClient |
| **CI/CD** | GitHub Actions |

## 📄 开源协议

[MIT License](LICENSE) — 自由使用、修改和分发。

---

<div align="center">

**Deep Photo** — 让 AI 帮你找到每一张珍贵的照片 📷

</div>
