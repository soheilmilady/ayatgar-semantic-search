# Ayatgar (اَیاتگار) — High-Speed Persian Semantic Search Engine

Ayatgar is a production-grade, hybrid semantic and textual search engine built to process and navigate massive classical Persian poetry datasets. Moving beyond simple keyword matching, Ayatgar utilizes vector embeddings to discover poems based on abstract concepts, emotions, and philosophical themes.

## 🚀 Key Features
- **Hybrid Search Architecture:** Combines fast textual pattern matching (`ILIKE` indexing) with deep semantic vector exploration using **pgvector**.
- **Local Embedded Intelligence:** Utilizes `intfloat/multilingual-e5-large-instruct` mapped onto local hardware capabilities (fully optimized for GPU VRAM execution).
- **Production-Ready Data Ingestion:** Includes custom high-speed local indexing scripts bypass systems, optimizing concurrent transaction injections directly into a structured PostgreSQL instance.
- **Modern Interactive UI:** A high-fidelity, responsive frontend built with TailwindCSS, dynamic speaker grouping, live statistical counters, and fully isolated modal renderers.

---

## 🏗️ Architectural Overview

### 1. Database Schema & Indexing
The storage layers are divided into relational entities optimized for fast similarity lookups:
- **Poems Table:** Holds metadata, full text mapping, and complete document embeddings.
- **Verses Table:** Maps individual verses, maintaining strict relational indexing (`FOREIGN KEY`) linked to parent records.
- **HNSW Indexing:** Employs Hierarchical Navigable Small World (`HNSW`) indexing charts (`vector_cosine_ops`) inside PostgreSQL to achieve sub-millisecond retrieval speeds over hundreds of thousands of items.

### 2. Backend & System Orchestration
Powered by **FastAPI** utilizing a connection pool strategy to maintain efficient multi-client query throughput.

---

## 📁 Repository Structure
```text
.
├── src/
│   ├── __init__.py
│   ├── main.py            # FastAPI Application & Search Controllers
│   └── database.py        # Database pooling configurations
├── scripts/
│   ├── local_indexer.py   # GPU-Accelerated embedding generator
│   └── db_importer.py     # Batch importer for optimized DB loading
├── ui/
│   └── index.html         # TailwindCSS-driven frontend application
├── .gitignore             # Protection rules filtering bytecode/local datasets
├── requirements.txt       # Dependencies manifest
└── README.md              # Documentation

🛠️ Quick Start
1. Set Up the Vector Database (Docker)
Ensure your local Docker environment is active, then spin up a PostgreSQL container equipped with pgvector:

Bash
docker run --name ayatgar-db -e POSTGRES_PASSWORD=ayatgar2024 -e POSTGRES_DB=ayatgar_db -p 5432:5432 -d pgvector/pgvector:pg16


2. Installation & Environment Configuration
Clone the repository and spin up your environment variables:

pip install -r requirements.txt


3. Run the Backend Server
Launch the API gateway locally:

python -m src.main
The server will boot up at http://127.0.0.1:8000. You can explore the interactive documentation schema at /docs.

Developed as a testament to building scalable, intelligent semantic applications bridging historical literature with cutting-edge AI orchestration.
