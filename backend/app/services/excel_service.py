from openpyxl import load_workbook
from openpyxl.drawing.image import Image as ExcelImage
from pathlib import Path
from typing import List
from datetime import datetime
import base64
from PIL import Image
import io
import os

def generate_excel(data: List[dict], save_dir: Path) -> Path:
    template_path = Path("uploads/template.xlsx")
    wb = load_workbook(template_path)
    ws = wb.active

    start_row = 9

    for i, entry in enumerate(data):
        row = start_row + i
        ws[f'B{row}'] = entry.get("no", "")
        ws[f'C{row}'] = entry.get("jalur", "")

        # Garis lintang dan bujur
        lat = entry.get("latitude", "")
        lon = entry.get("longitude", "")
        print(f"[DEBUG] Row {row}: Latitude={lat}, Longitude={lon}")
        ws[f'D{row}'] = lat
        ws[f'E{row}'] = lon

        # Cek kondisi
        kondisi = entry.get("kondisi", "").lower()
        if kondisi == "baik":
            ws[f'F{row}'] = "√"
        elif kondisi == "sedang":
            ws[f'G{row}'] = "√"
        elif kondisi == "buruk":
            ws[f'H{row}'] = "√"

        # Keterangan
        ws[f'I{row}'] = entry.get("keterangan", "")

        # Dokumentasi/foto
        image_data = entry.get("image")
        if image_data:
            try:
                if image_data.startswith("data:image"):
                    header, encoded = image_data.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                    img = Image.open(io.BytesIO(image_bytes))
                else:
                    if not os.path.exists(image_data):
                        raise FileNotFoundError(f"File tidak ditemukan: {image_data}")
                    img = Image.open(image_data)

                # Simpan gambar sementara secara unik
                img_temp_path = Path(f"temp_img_{row}.png")
                img.save(img_temp_path)

                excel_img = ExcelImage(str(img_temp_path))
                excel_img.width = 120
                excel_img.height = 90
                ws.add_image(excel_img, f'J{row}')
                print(f"[DEBUG] Gambar berhasil dimasukkan ke J{row}")

            except Exception as e:
                print(f"[ERROR] Gagal memasukkan gambar di baris {row}: {e}")

    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"output-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    save_path = save_dir / filename
    wb.save(save_path)

    return save_path
