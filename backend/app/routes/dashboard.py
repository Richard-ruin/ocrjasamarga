from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
from pathlib import Path
import shutil, uuid
from app.services.ocr_service import extract_coordinates_from_image
from app.services.excel_service import generate_excel
from app.config import temp_collection, history_collection
from app.constants import UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR
from fastapi.responses import FileResponse
from datetime import datetime
import json



router = APIRouter()

# 🟢 Upload dan Tambah Data Baru
@router.post("/add")
async def add_entry(
    jalur: str = Form(...),
    kondisi: str = Form(...),
    keterangan: str = Form(...),
    foto: UploadFile = File(...)
):
    ext = Path(foto.filename).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Format gambar tidak didukung")

    filename = f"{uuid.uuid4().hex}{ext}"
    saved_path = IMAGE_TEMP_DIR / filename

    with saved_path.open("wb") as buffer:
        shutil.copyfileobj(foto.file, buffer)

    lintang, bujur = extract_coordinates_from_image(str(saved_path))

    entry = {
        "no": temp_collection.count_documents({}) + 1,
        "jalur": jalur,
        "kondisi": kondisi,
        "keterangan": keterangan,
        "latitude": lintang,
"longitude": bujur,
        "foto_path": str(saved_path)
    }

    temp_collection.insert_one(entry)
    return {"message": "Data berhasil ditambahkan"}

# 🔵 Ambil Semua Data Sementara (Dashboard)
@router.get("/all")
def get_all_temp():
    data = list(temp_collection.find({}, {"_id": 0}))
    return data

# 🔴 Hapus Data Sementara Berdasarkan No
@router.delete("/delete/{no}")
def delete_entry(no: int):
    result = temp_collection.delete_one({"no": no})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return {"message": "Data berhasil dihapus"}

# 🟡 Generate File Excel dari Data Sementara
@router.post("/generate")
async def generate_file(
    images: List[UploadFile] = File(...),
    entries: List[str] = Form(...)
):
    # Parse JSON entries dari FormData
    parsed = [json.loads(e) for e in entries]
    if not parsed or len(parsed) != len(images):
        raise HTTPException(400, "Jumlah entries dan images tidak cocok")

    # Siapkan data lengkap untuk excel
    full_entries = []
    for i, (entry, img) in enumerate(zip(parsed, images), start=1):
        # Simpan gambar sementara
        ext = Path(img.filename).suffix
        fname = f"{uuid.uuid4().hex}{ext}"
        save_path = IMAGE_TEMP_DIR / fname
        with save_path.open("wb") as f:
            shutil.copyfileobj(img.file, f)

        # OCR: ambil lintang & bujur
        lintang, bujur = extract_coordinates_from_image(str(save_path))

        # Lengkapi entry
        entry_complete = {
            "no": i,
            "jalur": entry.get("jalur", ""),
            "lintang": lintang,
            "bujur": bujur,
            "kondisi": entry.get("kondisi", ""),
            "keterangan": entry.get("keterangan", ""),
            "foto_path": str(save_path),
        }
        full_entries.append(entry_complete)

    # Generate Excel dan kirim file sebagai response download
    save_dir = UPLOAD_DIR
    save_dir.mkdir(exist_ok=True)
    output_path = generate_excel(full_entries, save_dir)

    return FileResponse(
        path=str(output_path),
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# 🟣 Simpan dan Pindahkan ke History
@router.post("/save")
def save_to_history():
    data = list(temp_collection.find({}, {"_id": 0}))
    if not data:
        raise HTTPException(status_code=400, detail="Tidak ada data untuk disimpan")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_path = IMAGE_SAVED_DIR / timestamp
    folder_path.mkdir(parents=True, exist_ok=True)

    # Pindahkan gambar
    for d in data:
        original = Path(d["foto_path"])
        new_path = folder_path / original.name
        shutil.move(str(original), new_path)
        d["foto_path"] = str(new_path)

    history_collection.insert_one({
        "timestamp": timestamp,
        "data": data
    })

    temp_collection.delete_many({})
    return {"message": "Data berhasil disimpan"}
