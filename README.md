Ayatgar (آیاتگار) — High-Speed Persian Semantic Search Engine
Ayatgar is a production-grade, hybrid semantic and textual search engine built to process and navigate massive classical Persian poetry datasets. Moving beyond simple keyword matching, Ayatgar utilizes vector embeddings to discover poems based on abstract concepts, emotions, and philosophical themes.

Key Features
Hybrid Search Architecture: Combines fast textual pattern matching (ILIKE indexing) with deep semantic vector exploration using pgvector.

Local Embedded Intelligence: Utilizes intfloat/multilingual-e5-large-instruct mapped onto local hardware capabilities, fully optimized for GPU VRAM execution via FP16 precision.

Production-Ready Data Ingestion: Includes custom high-speed local indexing and import scripts, maximizing transaction throughput during data injection directly into a structured PostgreSQL instance running inside Docker.

Modern Interactive UI: A high-fidelity, responsive frontend built with TailwindCSS featuring dynamic speaker filtering, live statistical counters, and fully isolated modal renderers for reading full poems.

Architectural Overview
1. Database Schema & Indexing
The storage layers are divided into relational entities optimized for fast similarity lookups:

Poems Table: Holds global metadata, full text mapping, and complete document embeddings.

Verses Table: Maps individual verses, maintaining strict relational indexing (FOREIGN KEY) linked to parent records.

HNSW Indexing: Employs Hierarchical Navigable Small World (HNSW) indexing charts (vector_cosine_ops) inside PostgreSQL to achieve sub-millisecond retrieval speeds over hundreds of thousands of items.

2. Backend & System Orchestration
Powered by FastAPI utilizing a connection pool strategy to maintain efficient multi-client query throughput and optimized resource utilization.

Repository Structure
src/main.py: FastAPI Application & Search Controllers

src/database.py: Database pooling configurations

scripts/local_indexer.py: GPU-Accelerated embedding generator

scripts/db_importer.py: Batch importer for optimized DB loading

ui/index.html: TailwindCSS-driven frontend application

.gitignore: Protection rules filtering bytecode/local datasets

requirements.txt: Dependencies manifest

README.md: Documentation

Quick Start Guide
Step 1: Set Up the Vector Database via Docker
Ensure your local Docker environment is active, then spin up a PostgreSQL container equipped with pgvector by running the standard docker run command with your database credentials mapped to port 5432.

Step 2: Installation and Environment Configuration
Clone the repository to your local machine and install the required library manifests directly using the standard Python pip package manager against the requirements.txt file.

Step 3: Data Ingestion Pipeline
If you are setting up the database layers from scratch on your local machine, execute the local indexer script inside the scripts folder to generate the GPU embeddings. Once finished, run the database importer script to safely stream the generated vectors into your running Docker container.

Step 4: Run the Backend API Server
Launch the FastAPI gateway locally by executing the module runner command against the src application directory. The API backend will automatically boot up locally on port 8000, allowing you to access the interactive Swagger documentation interface directly at the docs endpoint.

Developed as a testament to building scalable, intelligent semantic applications bridging historical literature with cutting-edge AI orchestration.
