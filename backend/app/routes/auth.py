from fastapi import APIRouter, HTTPException
from app.models.schemas import LoginRequest
import os

router = APIRouter()

# Ambil username dan password dari .env
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

@router.post("/login")
def login(request: LoginRequest):
    if request.username == ADMIN_USERNAME and request.password == ADMIN_PASSWORD:
        return {"message": "Login berhasil"}
    raise HTTPException(status_code=401, detail="Username atau password salah")
