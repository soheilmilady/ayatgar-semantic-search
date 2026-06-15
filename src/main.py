import torch
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from contextlib import asynccontextmanager
from src.database import initialize_db_pool, close_db_pool, get_db_connection

MODEL_NAME = "intfloat/multilingual-e5-large-instruct"
device     = "cuda" if torch.cuda.is_available() else "cpu"

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_db_pool()
    yield
    close_db_pool()

app = FastAPI(
    title="Ayatgar API Backend",
    description="High-Speed Hybrid (Semantic & Textual) Search Engine for Persian Poetry",
    version="1.1.6",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Embedding Model
model = SentenceTransformer(MODEL_NAME, device=device)

# Pydantic Schemas
class SearchResult(BaseModel):
    verse_id: int
    poem_id: int
    text: str
    poet: str
    cat_path: str
    score: Optional[float] = None

class VerseResponse(BaseModel):
    id: int
    verse_order: int
    position: int
    text: str

class PoemResponse(BaseModel):
    id: int
    ganjoor_id: int
    title: str
    full_title: str
    poet: str
    cat_path: str
    url: Optional[str] = None
    full_text: Optional[str] = None
    verse_count: int
    verses: List[VerseResponse]

class StatsResponse(BaseModel):
    total_poems: int
    total_verses: int
    total_poets: int

@app.get("/api/stats", response_model=StatsResponse)
def get_database_stats():
    with get_db_connection() as cur:
        cur.execute("SELECT COUNT(*) FROM poems;")
        total_poems = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM verses;")
        total_verses = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT poet) FROM poems;")
        total_poets = cur.fetchone()[0]
        
    return StatsResponse(
        total_poems=total_poems,
        total_verses=total_verses,
        total_poets=total_poets
    )

@app.get("/search/semantic", response_model=List[SearchResult])
def search_semantic(query: str, limit: int = 10, poets: Optional[List[str]] = Query(None)):
    instructed_query = f"query: {query}"
    
    with torch.no_grad():
        embedding = model.encode(instructed_query, convert_to_tensor=False, normalize_embeddings=True)
    embedding_list = embedding.tolist()

    sql = """
        SELECT v.id, v.poem_id, v.text, p.poet, p.cat_path, (v.embedding <=> %s::vector) as distance
        FROM verses v
        JOIN poems p ON v.poem_id = p.id
        WHERE (v.embedding <=> %s::vector) <= 0.13
    """
    params = [embedding_list, embedding_list]

    if poets and len(poets) > 0:
        sql += " AND p.poet = ANY(%s)"
        params.append(poets)

    sql += " ORDER BY distance ASC LIMIT %s;"
    params.append(limit)

    results = []
    with get_db_connection() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        
        for r in rows:
            score = round((1.0 - r[5]) * 100, 1)
            results.append(SearchResult(
                verse_id=r[0], poem_id=r[1], text=r[2],
                poet=r[3], cat_path=r[4], score=score
            ))
            
    return results

@app.get("/search/text", response_model=List[SearchResult])
def search_text(keyword: str, limit: int = 10, poets: Optional[List[str]] = Query(None)):
    if not keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword cannot be empty")

    kw_fa = keyword.strip().replace("ي", "ی").replace("ك", "ک")
    kw_ar = keyword.strip().replace("ی", "ي").replace("ک", "ك")

    results = []

    with get_db_connection() as cur:
        sql_verses = """
            SELECT v.id, v.poem_id, v.text, p.poet, p.cat_path
            FROM verses v
            JOIN poems p ON v.poem_id = p.id
            WHERE (v.text ILIKE %s OR v.text ILIKE %s)
        """
        params_verses = [f"%{kw_fa}%", f"%{kw_ar}%"]

        if poets and len(poets) > 0:
            sql_verses += " AND p.poet = ANY(%s)"
            params_verses.append(poets)

        sql_verses += " LIMIT %s;"
        params_verses.append(limit)

        cur.execute(sql_verses, tuple(params_verses))
        rows = cur.fetchall()
        for r in rows:
            results.append(SearchResult(
                verse_id=r[0], poem_id=r[1], text=r[2], poet=r[3], cat_path=r[4],
                score=100.0
            ))

        if len(results) < limit:
            remaining_limit = limit - len(results)
            
            sql_poems = """
                SELECT id, title, poet, cat_path, full_text
                FROM poems
                WHERE (full_text ILIKE %s OR full_text ILIKE %s)
            """
            params_poems = [f"%{kw_fa}%", f"%{kw_ar}%"]

            if poets and len(poets) > 0:
                sql_poems += " AND poet = ANY(%s)"
                params_poems.append(poets)

            sql_poems += " LIMIT %s;"
            params_poems.append(remaining_limit)

            cur.execute(sql_poems, tuple(params_poems))
            poem_rows = cur.fetchall()
            for pr in poem_rows:
                lines = pr[4].split('\n')
                matched_line = f"یافت شده در متن اثر: {pr[1]}"
                for line in lines:
                    if kw_fa in line or kw_ar in line:
                        matched_line = line.strip()
                        break
                
                results.append(SearchResult(
                    verse_id=0, poem_id=pr[0], text=matched_line, poet=pr[2], cat_path=pr[3], score=100.0
                ))

    return results[:limit]

@app.get("/poem/{poem_id}", response_model=PoemResponse)
def get_poem_details(poem_id: int):
    with get_db_connection() as cur:
        cur.execute("""
            SELECT id, ganjoor_id, title, full_title, poet, cat_path, url, full_text, verse_count
            FROM poems WHERE id = %s;
        """, (poem_id,))
        poem_row = cur.fetchone()

        if not poem_row:
            raise HTTPException(status_code=404, detail="Poem not found")

        cur.execute("""
            SELECT id, verse_order, position, text FROM verses
            WHERE poem_id = %s ORDER BY verse_order ASC, position ASC;
        """, (poem_id,))
        verse_rows = cur.fetchall()

    verses_list = []
    for v in verse_rows:
        verses_list.append(VerseResponse(id=v[0], verse_order=v[1], position=v[2], text=v[3]))

    return PoemResponse(
        id=poem_row[0], ganjoor_id=poem_row[1], title=poem_row[2],
        full_title=poem_row[3], poet=poem_row[4], cat_path=poem_row[5],
        url=poem_row[6], full_text=poem_row[7], verse_count=poem_row[8],
        verses=verses_list
    )

@app.get("/poets", response_model=List[str])
def get_all_poets():
    with get_db_connection() as cur:
        cur.execute("SELECT DISTINCT poet FROM poems WHERE poet IS NOT NULL ORDER BY poet ASC;")
        rows = cur.fetchall()
    return [r[0] for r in rows]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)