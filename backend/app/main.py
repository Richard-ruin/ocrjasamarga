# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import semua routes
from app.routes import auth, dashboard, jadwal, inspeksi, history
from app.constants import UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR

app = FastAPI(
    title="OCR Jasa Marga Backend",
    description="Backend API untuk sistem inspeksi lapangan dengan OCR",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Bisa disesuaikan untuk keamanan
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Buat direktori jika belum ada
for directory in [UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Mount static files untuk serving images
app.mount("/static", StaticFiles(directory=str(IMAGE_SAVED_DIR)), name="static")

# Include all routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(jadwal.router, prefix="/api", tags=["Jadwal"])
app.include_router(inspeksi.router, prefix="/api", tags=["Inspeksi"])
app.include_router(history.router, prefix="/api", tags=["History"])

@app.get("/")
def read_root():
    return {
        "message": "OCR Jasa Marga Backend v2.0 is running",
        "features": [
            "Admin authentication with JWT",
            "Jadwal CRUD operations",
            "Inspeksi with OCR coordinates",
            "History management",
            "Dashboard statistics"
        ]
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-07-02T12:00:00Z",
        "version": "2.0.0"
    }

@app.get("/api/info")
def api_info():
    """API information endpoint"""
    return {
        "api_version": "2.0.0",
        "endpoints": {
            "auth": [
                "POST /api/auth/register",
                "POST /api/auth/login", 
                "POST /api/auth/logout",
                "GET /api/auth/me"
            ],
            "jadwal": [
                "GET /api/jadwal",
                "POST /api/jadwal",
                "PUT /api/jadwal/{id}",
                "DELETE /api/jadwal/{id}"
            ],
            "inspeksi": [
                "POST /api/inspeksi/add",
                "GET /api/inspeksi/all",
                "POST /api/inspeksi/generate",
                "POST /api/inspeksi/save"
            ],
            "dashboard": [
                "GET /api/dashboard/stats",
                "GET /api/dashboard/recent-jadwal"
            ],
            "history": [
                "GET /api/history",
                "DELETE /api/history/{id}",
                "POST /api/generate-from-history/{id}"
            ]
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)