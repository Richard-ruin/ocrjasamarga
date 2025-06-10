# OCRJasaMarga

Sistem otomatisasi ekstraksi data koordinat dan dokumentasi dari form "Monitoring Patok RUMIJA" milik Jasa Marga menggunakan OCR dan menghasilkan file Excel sesuai template.

## 🔧 Fitur Utama

- Upload gambar form patok RUMIJA (format `.jpg` / `.png`)
- Ekstraksi otomatis:
  - Garis Lintang (Latitude) & Garis Bujur (Longitude) via OCR
  - Kondisi patok (baik/sedang/buruk)
  - Keterangan & Jalur
- Gambar dimasukkan langsung ke Excel (kolom Dokumentasi)
- Hasil akhir dalam format `.xlsx` sesuai template resmi
- Backend menggunakan **FastAPI**
- Frontend (dalam pengembangan) menggunakan **React + Tailwind CSS**
- Database **MongoDB** untuk penyimpanan riwayat input

---

## 🚀 Cara Menjalankan Backend

### 1. Kloning Repo
```bash
git clone https://github.com/username/ocrjasamarga.git
cd ocrjasamarga/backend
```

### 2. Buat Virtual Environment & Install Dependensi
```bash
python -m venv venv
venv\Scripts\activate   # Untuk Windows
# source venv/bin/activate   # Untuk Linux/Mac

pip install -r requirements.txt
```

### 3. Jalankan FastAPI
```bash
uvicorn app.main:app --reload
```

---

## 🖼️ Struktur Input Gambar

Gambar input berupa foto formulir patok yang mengandung informasi:
- Jalur
- Garis Lintang & Bujur (format: `-6.123456, 106.789012`)
- Kondisi (baik / sedang / buruk)
- Keterangan

Koordinat akan diekstraksi menggunakan [EasyOCR](https://github.com/JaidedAI/EasyOCR) secara otomatis.

---

## 📁 Struktur Proyek (Backend)

```
ocrjasamarga/
├── app/
│   ├── main.py                # Entry point FastAPI
│   ├── routes/
│   │   └── dashboard.py       # Endpoint /generate
│   ├── services/
│   │   ├── ocr_service.py     # Ekstraksi koordinat via OCR
│   │   └── excel_service.py   # Penyusunan file Excel
├── uploads/                   # Tempat file template & hasil output
├── images/temp/               # Tempat simpan gambar sementara
├── requirements.txt
```

---

## 📄 Format Template Excel

- Mulai input dari baris ke-9 (`B9`)
- Kolom:
  - **B**: No
  - **C**: Jalur
  - **D**: Garis Lintang
  - **E**: Garis Bujur
  - **F**: ✔ untuk "Baik"
  - **G**: ✔ untuk "Sedang"
  - **H**: ✔ untuk "Buruk"
  - **I**: Keterangan
  - **J**: Foto/Dokumentasi

---

## 🧪 Testing Lokal (tanpa frontend)

Gunakan Postman / curl:

**POST** `http://127.0.0.1:8000/api/generate`  
**Form-Data:**
- `images`: Upload 1 atau lebih gambar
- `entries`: JSON string per data, contoh:
  ```json
  {
    "jalur": "Arah Jakarta",
    "kondisi": "baik",
    "keterangan": "Patok terlihat jelas"
  }
  ```

---

## 📦 TODO Selanjutnya

- [ ] Integrasi frontend React
- [ ] Validasi posisi koordinat via map
- [ ] Export ke PDF (opsional)
- [ ] Autentikasi admin (opsional)

---

## 🧠 Teknologi Digunakan

- **FastAPI** - REST backend
- **EasyOCR** - Optical Character Recognition
- **openpyxl** - Manipulasi file Excel
- **MongoDB** - Penyimpanan entri (via `temp_entries` dan `saved_tables`)
- **Pillow (PIL)** - Manipulasi gambar
- **React + Tailwind** (Frontend - dalam proses)

---

## 🧑‍💻 Developer

Proyek ini dikembangkan untuk mempermudah digitalisasi pengawasan patok RUMIJA oleh tim internal atau mitra Jasa Marga.

---

## 🏁 Lisensi

Lisensi internal (atau sesuaikan). Tidak untuk distribusi publik kecuali atas izin resmi.
