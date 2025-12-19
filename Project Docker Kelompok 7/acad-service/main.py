from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from contextlib import contextmanager

app = FastAPI(title="Product Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'products'),
    'user': os.getenv('DB_USER', 'productuser'),
    'password': os.getenv('DB_PASSWORD', 'productpass')
}

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

class Mahasiswa(BaseModel):
    nim: str
    nama: str
    jurusan: str
    angkatan: int = Field(ge=0)

# Database connection pool
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.on_event("startup")
async def startup_event():
    try:
        with get_db_connection() as conn:
            print("Acad Service: Connected to PostgreSQL")
    except Exception as e:
        print(f"Acad Service: PostgreSQL connection error: {e}")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "Acad Service is running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/acad/mahasiswa")
async def get_mahasiswas():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM mahasiswa"

            cursor.execute(query)
            rows = cursor.fetchall()

            return [{"nim": row[0], "nama": row[1], "jurusan": row[2], "angkatan": row[3]} for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/acad/ips")
async def get_ips(nim: str = Query(..., description="NIM mahasiswa, contoh: 22002")):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    m.nim,
                    m.nama,
                    m.jurusan,
                    krs.nilai,
                    mk.sks
                FROM mahasiswa m
                JOIN krs ON krs.nim = m.nim
                JOIN mata_kuliah mk ON mk.kode_mk = krs.kode_mk
                WHERE m.nim = %s
            """

            cursor.execute(query, (nim,))
            rows = cursor.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"Data KRS untuk NIM {nim} tidak ditemukan")

        bobot_nilai = {
            "A": 4.0,
            "A-": 3.75,
            "B+": 3.5,
            "B": 3.0,
            "B-": 2.75,
            "C+": 2.5,
            "C": 2.0,
            "D": 1.0,
            "E": 0.0
        }

        total_sks = 0
        total_bobot = 0.0

        nim_mhs, nama_mhs, jurusan_mhs = rows[0][0], rows[0][1], rows[0][2]

        detail = []
        for row in rows:
            nilai_huruf = str(row[3]).strip().upper()   
            sks = int(row[4])                           

            if nilai_huruf not in bobot_nilai:
                raise HTTPException(
                    status_code=400,
                    detail=f"Nilai '{nilai_huruf}' tidak dikenali. Harus salah satu: {list(bobot_nilai.keys())}"
                )

            bobot = bobot_nilai[nilai_huruf]
            total_sks += sks
            total_bobot += bobot * sks

            detail.append({
                "nilai": nilai_huruf,
                "sks": sks,
                "bobot": bobot,
                "bobot_x_sks": round(bobot * sks, 2)
            })

        if total_sks == 0:
            raise HTTPException(status_code=400, detail="Total SKS = 0, IPS tidak bisa dihitung")

        ips = total_bobot / total_sks

        return {
            "nim": nim_mhs,
            "nama": nama_mhs,
            "jurusan": jurusan_mhs,
            "total_sks": total_sks,
            "total_bobot": round(total_bobot, 2),
            "ips": round(ips, 2),
            "detail_perhitungan": detail
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
