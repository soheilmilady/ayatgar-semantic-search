# Ayatgar (آیاتگار) — High-Speed Persian Semantic Search Engine

Ayatgar is a production-grade, hybrid semantic and textual search engine built to process and navigate massive classical Persian poetry datasets[cite: 1, 2]. 

---

## 🚀 Key Features

* **Hybrid Search:** Combines fast textual matching (`ILIKE`) with deep semantic exploration using **pgvector**[cite: 1, 2].
* **AI Intelligence:** Utilizes `intfloat/multilingual-e5-large-instruct` optimized for GPU execution[cite: 1, 3].
* **High-Speed Ingestion:** Custom scripts for batch vector injection into PostgreSQL[cite: 2, 3].
* **Modern UI:** Responsive frontend built with TailwindCSS[cite: 5].

---

## 🏗️ Architectural Overview

### 1. Database Schema
* **Poems Table:** Metadata, full text, and document embeddings[cite: 2, 3].
* **Verses Table:** Relational verse mapping with foreign keys[cite: 2, 3].
* **HNSW Indexing:** Optimized for sub-millisecond similarity search[cite: 2].

### 2. Backend
Powered by **FastAPI** with connection pooling for high-concurrency throughput[cite: 1, 2].

---

## 📁 Repository Structure

.
├── src/
│   ├── main.py            # FastAPI Application
│   └── database.py        # Database configurations
├── scripts/
│   ├── local_indexer.py   # GPU embedding generator
│   └── db_importer.py     # Batch data importer
├── ui/
│   └── index.html         # TailwindCSS Frontend
├── .gitignore             # Protection rules
└── requirements.txt       # Dependencies

---

## 🛠️ Quick Start

### Step 1: Set Up Docker Database
Run a PostgreSQL container with the pgvector extension:

docker run --name ayatgar-db -e POSTGRES_PASSWORD=ayatgar2024 -e POSTGRES_DB=ayatgar_db -p 5432:5432 -d pgvector/pgvector:pg16

### Step 2: Install Dependencies
pip install -r requirements.txt

### Step 3: Run Data Pipeline
Generate embeddings and import them into the database:

python scripts/local_indexer.py
python scripts/db_importer.py

### Step 4: Launch API
python -m src.main

Access the documentation at: http://127.0.0.1:8000/docs

---
*Developed as a testament to building scalable, intelligent semantic applications.*
