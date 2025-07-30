# app/main.py - Updated with new routes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import semua routes
from app.routes import auth, dashboard, jadwal, inspeksi, history, aset
from app.constants import UPLOAD_DIR, IMAGE_TEMP_DIR, IMAGE_SAVED_DIR

app = FastAPI(
    title="OCR Jasa Marga Backend v3.0",
    description="Backend API untuk sistem inspeksi lapangan dengan OCR, Role-based Access, dan Kelola Aset",
    version="3.0.0"
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
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication & User Management"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(aset.router, prefix="/api", tags=["Kelola Aset"])  # New route
app.include_router(jadwal.router, prefix="/api", tags=["Jadwal"])
app.include_router(inspeksi.router, prefix="/api", tags=["Inspeksi"])
app.include_router(history.router, prefix="/api", tags=["History"])

@app.get("/")
def read_root():
    return {
        "message": "OCR Jasa Marga Backend v3.0 is running",
        "new_features": [
            "Role-based access control (Admin & Petugas)",
            "Kelola Aset management",
            "Jadwal-based inspection workflow",
            "Enhanced Excel generation with asset info",
            "Asset integration in scheduling"
        ],
        "user_roles": {
            "admin": [
                "Kelola User (CRUD users)",
                "Full access to all data",
                "System administration"
            ],
            "petugas": [
                "Kelola Aset",
                "Kelola Jadwal", 
                "Inspeksi",
                "History",
                "Dashboard"
            ]
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-07-30T12:00:00Z",
        "version": "3.0.0",
        "features": [
            "Role-based authentication",
            "Asset management",
            "Schedule-based inspections",
            "Enhanced reporting"
        ]
    }

@app.get("/api/info")
def api_info():
    """API information endpoint with updated features"""
    return {
        "api_version": "3.0.0",
        "endpoints": {
            "auth": [
                "POST /api/auth/register - Register new user (admin/petugas)",
                "POST /api/auth/login - Login user", 
                "POST /api/auth/logout - Logout user",
                "GET /api/auth/me - Get current user info",
                "PUT /api/auth/profile - Update profile",
                # Admin only
                "GET /api/auth/users - List all users (ADMIN ONLY)",
                "POST /api/auth/users - Create new user (ADMIN ONLY)",
                "PUT /api/auth/users/{id} - Update user (ADMIN ONLY)",
                "DELETE /api/auth/users/{id} - Delete user (ADMIN ONLY)",
                "PUT /api/auth/users/{id}/status - Toggle user status (ADMIN ONLY)"
            ],
            "aset": [
                "GET /api/aset - Get all assets",
                "GET /api/aset/paginated - Get assets with pagination",
                "GET /api/aset/{id} - Get asset by ID",
                "POST /api/aset - Create new asset",
                "PUT /api/aset/{id} - Update asset",
                "DELETE /api/aset/{id} - Delete asset",
                "GET /api/aset/status/{status} - Get assets by status",
                "GET /api/aset/jenis/{jenis} - Get assets by type",
                "GET /api/aset/stats - Get asset statistics"
            ],
            "jadwal": [
                "GET /api/jadwal - Get all schedules (with asset info)",
                "POST /api/jadwal - Create new schedule (requires asset)",
                "PUT /api/jadwal/{id} - Update schedule",
                "DELETE /api/jadwal/{id} - Delete schedule",
                "GET /api/jadwal/status/{status} - Get schedules by status",
                "GET /api/jadwal/today - Get today's schedules",
                "GET /api/jadwal/aset/{id_aset} - Get schedules by asset",
                "GET /api/jadwal/stats - Get schedule statistics"
            ],
            "inspeksi": [
                # New jadwal-based workflow
                "GET /api/inspeksi/jadwal - Get schedules ready for inspection",
                "POST /api/inspeksi/start/{jadwal_id} - Start inspection from schedule",
                "POST /api/inspeksi/add - Add inspection entry (requires jadwal_id)",
                "GET /api/inspeksi/cache/{jadwal_id} - Get cache data by schedule",
                "DELETE /api/inspeksi/delete/{jadwal_id}/{no} - Delete cache entry",
                "POST /api/inspeksi/generate/{jadwal_id} - Generate Excel by schedule",
                "POST /api/inspeksi/save/{jadwal_id} - Save inspection & complete schedule",
                "POST /api/inspeksi/generate-from-cache/{jadwal_id} - Generate from cache by schedule",
                # Legacy endpoints (backward compatibility)
                "GET /api/inspeksi/all - Get all cache data",
                "GET /api/inspeksi/stats - Get inspection statistics"
            ],
            "dashboard": [
                "GET /api/dashboard/stats - Get dashboard statistics",
                "GET /api/dashboard/recent-jadwal - Get recent schedules"
            ],
            "history": [
                "GET /api/history - Get inspection history",
                "DELETE /api/history/{id} - Delete history entry",
                "POST /api/generate-from-history/{id} - Generate Excel from history"
            ]
        },
        "workflow": {
            "new_inspection_flow": [
                "1. Admin/Petugas creates Asset in Kelola Aset",
                "2. Create Jadwal with selected Asset",
                "3. Go to Inspeksi menu -> Select Jadwal -> Click 'Inspeksi' button",
                "4. Add inspection entries with photos",
                "5. Generate Excel or Save inspection",
                "6. Jadwal status automatically updated to 'completed'"
            ]
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)