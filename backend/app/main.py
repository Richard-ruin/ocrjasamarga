from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, dashboard, history
from pathlib import Path

app = FastAPI()

# CORS (agar frontend bisa akses backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Boleh disesuaikan untuk keamanan
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
IMAGE_TEMP_DIR = Path("images/temp")

# Routing
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(history.router, prefix="/api", tags=["History"])

@app.get("/")
def read_root():
    return {"message": "OCR Jasa Marga Backend is running"}
