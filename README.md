# Local Vision Search v2.0

Privacy-first, AI-powered local photo organizer and search engine. Runs entirely offline on your device using state-of-the-art open source models.

## 🚀 Key Features

- **Semantic Search**: Search your photos using natural language (e.g., "cat sleeping on sofa", "sunset at the beach").
- **Smart Organization**:
  - **"On This Day"**: Rediscover memories from previous years.
  - **People**: Automatically groups faces using advanced clustering.
  - **Map View**: Visualize your photos on an interactive global map.
  - **Timeline**: Browse your life in a chronological stream with "Best Shot" highlighting.
- **Privacy First**: All processing (indexing, embedding, facial recognition) happens locally. No data leaves your machine.

## 🛠 Technology Stack

This project is built with a modern stack designed for performance and local deployment:

- **Frontend**: [Vue 3](https://vuejs.org/) + [TailwindCSS](https://tailwindcss.com/) - Provides a responsive, beautiful, and fluid user interface.
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) - High-performance Python generic framework for serving the REST API.
- **Vector Database**: [ChromaDB](https://www.trychroma.com/) - Stores image and text embeddings for efficient semantic retrieval.
- **Metadata Store**: [SQLite](https://www.sqlite.org/) - Lightweight, serverless database for file paths, timestamps, and relations.

## 🧠 AI Models

We leverage powerful open-source models to understand your photos:

### 1. Vision & Language
**Model**: [Google SigLIP (SO400M)](https://huggingface.co/google/siglip-so400m-patch14-384)
- **Role**: Core Search Engine.
- **Function**: Converts both your images and your text queries into a shared mathematical vector space. This allows the system to understand that a picture of a "gongbi hua" matches the query "Chinese painting" even if the filename is `IMG_1234.jpg`.

### 2. Intelligent Translation
**Model**: [Qwen2.5 (0.5B & 7B)](https://huggingface.co/Qwen)
- **Role**: Localization & Query Understanding.
- **Function**:
  - **0.5B (Nano)**: Runs purely locally for low-latency translation of search queries (e.g., automatically translating Chinese queries to English to better match the Vision model's training data).
  - **7B (Large)**: Loaded on-demand for high-precision tasks, such as translating complex location names for the Map view.

### 3. Face Recognition
**Model**: [InsightFace (buffalo_l)](https://github.com/deepinsight/insightface)
- **Role**: People Organization.
- **Function**: Detects faces in photos, extracts facial features, and clusters them to identify unique individuals. Enables the "People" view to browse photos by person.

## 📦 Installation & Setup

1. **Backend**:
   ```bash
   pip install -r requirements.txt
   python -m src.main_cli
   ```

2. **Frontend**:
   ```bash
   cd web
   npm install
   npm run dev
   ```

3. **Usage**:
   Open `http://localhost:5173` in your browser. Configure your photo folders in the Settings page to start indexing.

## 📜 License

MIT
