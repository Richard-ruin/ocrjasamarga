import easyocr
import re
from typing import Tuple

reader = easyocr.Reader(['en'], gpu=False)

def extract_coordinates_from_image(image_path: str) -> Tuple[str, str]:
    result = reader.readtext(image_path, detail=0)
    text = " ".join(result)

    # Regex untuk lintang dan bujur (format desimal: -6.123456, 106.987654)
    pattern = r"(-?\d{1,2}\.\d+)[ ,;:/\\|-]+(-?\d{2,3}\.\d+)"
    match = re.search(pattern, text)

    if match:
        lintang, bujur = match.groups()
        return lintang, bujur
    else:
        return "", ""
