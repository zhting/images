本地生成式视觉检索系统 - 开发需求说明书版本: 1.0密级: 内部公开核心目标: 构建一个隐私优先的本地图片检索系统，利用“生成式查询扩展”技术，通过自然语言描述生成目标图像锚点，并在本地海量图库中进行视觉相似度匹配。1. 系统设计哲学1.1 核心逻辑传统的文本搜图（Text-to-Image Retrieval）往往依赖于模型对文本的理解，存在语义鸿沟。本系统引入**“生成”**作为中间层：用户输入 -> 生图接口 -> 生成临时目标图 (Proxy Image)目标图 -> 视觉编码器 -> 本地向量匹配 -> 返回本地真实照片1.2 架构原则生图解耦 (Decoupling Generation)：生图模块设计为通用接口，不绑定任何特定供应商。本地闭环 (Local Loop)：除了生图调用外部 API，所有索引建立、向量存储、图片检索均在本地离线完成，确保私有相册不上传云端。零侵入 (Zero-Intrusion)：不修改用户原始文件，仅读取并建立索引。实时性 (Real-time)：感知文件系统的增删改，并实时更新索引。2. 核心模块详细需求系统划分为四个核心子模块：生成适配层、视觉计算层、持久化存储层、文件监控层。2.1 模块 A：生图适配层 (Generative Adapter Layer)功能目标：提供一个统一的抽象接口，用于对接第三方生图 API。开发阶段可使用 Mock 数据，后续可接入 DALL-E 3, Midjourney 或 Stable Diffusion。技术规范：设计模式：必须采用 策略模式 (Strategy Pattern) 或 适配器模式。接口定义 (Python)：Pythonfrom abc import ABC, abstractmethod
from typing import Optional
from PIL import Image

class IImageGenerator(ABC):
    """
    生成服务抽象基类
    """
    @abstractmethod
    def generate(self, 
                 prompt: str, 
                 reference_image: Optional[Image.Image] = None, 
                 strength: float = 0.7) -> Image.Image:
        """
        Args:
            prompt: 用户输入的自然语言描述
            reference_image: (可选) 用户上传的参考草图/图片
            strength: (可选) 图生图的重绘幅度，0.0-1.0
        Returns:
            生成的 PIL Image 对象
        """
        pass

# 示例：开发阶段的 Mock 实现
class MockGenerator(IImageGenerator):
    def generate(self, prompt, reference_image=None, strength=0.7):
        # 返回一张本地的占位符图片用于测试流程
        return Image.open("./assets/placeholder.jpg")
输入处理：接口需支持纯文本 Prompt 输入，以及“参考图 + 文本”的混合输入。2.2 模块 B：数据管理与临时存储 (Data & Temp Store)功能目标：管理生成的临时图片（作为检索中间态）以及系统的配置信息。技术规范：数据库选型：SQLite (无需部署，单文件)。生成记录表 (generation_history)：id (UUID): 唯一标识。prompt (Text): 用户的原始提示词。image_blob (Blob): 生成图片的二进制数据（建议存储压缩后的 JPG 以节省空间）。created_at (DateTime): 生成时间。api_provider (Varchar): 记录是由哪个 API 生成的 (如 "mock", "openai", "sd")。生命周期管理：实现后台清理任务：当临时表占用超过 500MB 或记录超过 7 天，自动清理旧数据。2.3 模块 C：本地索引与向量库 (Local Indexing & Vector DB)功能目标：对本地硬盘的照片进行特征提取和向量存储，支持毫秒级检索。技术规范：向量数据库：Milvus Lite (pip install pymilvus)。优势：纯 Python 库运行，无 Docker 依赖，数据存储为本地文件 search.db 1。视觉模型 (Encoder)：CLIP (ViT-B-32) 或 DINOv2。建议使用 sentence-transformers 库加载 CLIP 模型，并将模型权重下载至本地缓存，确保无网状态下也能进行检索（生图除外）。Collection Schema 设计：Collection Name: LocalPhotoGalleryid (Int64, AutoID): 主键。vector (FloatVector, Dim=512): 图片特征向量。file_path (VarChar, 1024): 图片绝对路径。file_hash (VarChar, 64): 文件内容哈希（用于去重）。last_modified (Int64): 文件修改时间戳。索引配置：类型：HNSW参数：M=16, efConstruction=200 (平衡构建速度与查询精度)。2.4 模块 D：文件系统实时监控 (File Watcher)功能目标：自动化维护本地文件夹与向量库的一致性。技术规范：依赖库：Watchdog (Python) 3。核心逻辑：全量扫描 (Startup)：系统启动时，使用 os.scandir (比 os.walk 快 10-20 倍) 遍历目标目录 5。对比数据库中的 file_path 和 last_modified，识别新增或修改的文件。增量监控 (Runtime)：on_created: 触发【特征提取 -> 插入向量库】流程。on_deleted: 触发【根据路径查询 ID -> 删除向量】流程。on_moved: 触发【删除旧路径向量 -> 插入新路径向量】流程。防抖动 (Debounce)：文件保存时可能会触发多次 modified 事件，需实现 1-2 秒的防抖逻辑，避免对同一文件重复计算向量。3. 业务流程 (Workflows)3.1 索引构建流程 (后台自动运行)用户指定本地照片目录（如 D:/MyPhotos）。File Watcher 扫描该目录。发现未索引图片 -> 读取图片 -> 预处理 (Resize/Normalize)。输入 Vision Model (CLIP) -> 获得 512维 Vector。写入 Milvus Lite -> 完成索引。3.2 搜索流程 (用户交互)输入：用户输入 "一只在雪地里奔跑的哈士奇"。生图：调用 IImageGenerator.generate("Runing husky in snow")。注：此处调用的是抽象接口，具体是 Mock 还是真实 API 由配置决定。反馈：界面展示生成的“哈士奇”图片，用户确认满意。编码：将这张生成的图片输入 Vision Model -> 获得查询向量 $V_{query}$。检索：在 Milvus Lite 中搜索与 $V_{query}$ 余弦相似度最高的 Top 50 个向量。展示：根据返回的 file_path，加载本地真实照片并展示给用户。4. 技术栈推荐层次推荐技术理由语言Python 3.10+强类型支持，AI 生态丰富API 框架FastAPI高性能，易于构建内部接口向量库Milvus Lite轻量级，支持本地文件存储，生产级性能ORMSQLAlchemy (SQLite)管理元数据和生成历史AI 模型加载HuggingFace / PyTorch加载 CLIP/DINOv2 模型文件监控Watchdog跨平台文件系统事件监听前端 (可选)Streamlit / NiceGUI快速构建 Python 原生 UI5. 开发阶段里程碑Phase 1 (原型验证):实现 MockGenerator。跑通 CLIP + Milvus Lite 的本地索引和检索流程。实现简单的 CLI 工具：输入图片路径 -> 返回最相似图片。Phase 2 (接口对接):实现 OpenAIGenerator 或 StabilityGenerator 适配器，替换 Mock。接入 SQLite 存储生成历史。Phase 3 (实时同步):集成 Watchdog，实现文件系统的自动感知。开发前端 UI。