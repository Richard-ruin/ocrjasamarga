from pathlib import Path

# Path untuk folder upload dan gambar
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
IMAGE_TEMP_DIR = BASE_DIR / "images" / "temp"
IMAGE_SAVED_DIR = BASE_DIR / "images" / "saved"

# Ekstensi file yang diizinkan untuk upload
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Buat folder jika belum ada
for path in [UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR]:
    path.mkdir(parents=True, exist_ok=True)
