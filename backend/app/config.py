# app/config.py
import os
from pymongo import MongoClient
from dotenv import load_dotenv
import bcrypt
from datetime import datetime

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
temp_collection = db["temp_entries"]
history_collection = db["saved_tables"]
admin_collection = db["admins"]
jadwal_collection = db["jadwal"]
inspeksi_collection = db["inspeksi"]

def create_default_admin():
    """Buat admin default jika belum ada"""
    try:
        # Cek apakah sudah ada admin
        if admin_collection.count_documents({}) == 0:
            # Ambil dari environment variables
            username = os.getenv("ADMIN_USERNAME", "admin")
            password = os.getenv("ADMIN_PASSWORD", "admin123")
            
            # Hash password
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            # Buat admin default
            default_admin = {
                "username": username,
                "email": "admin@ocrjasamarga.com",
                "password": hashed_password.decode('utf-8'),
                "full_name": "Administrator",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "last_login": None
            }
            
            result = admin_collection.insert_one(default_admin)
            if result.inserted_id:
                print(f"✅ Default admin created: {username}")
            else:
                print("❌ Failed to create default admin")
        else:
            print("✅ Admin collection already exists")
            
    except Exception as e:
        print(f"❌ Error creating default admin: {e}")

def migrate_existing_data():
    """Migrate existing data untuk menambahkan admin_id"""
    try:
        # Ambil admin pertama sebagai default owner
        first_admin = admin_collection.find_one({})
        if not first_admin:
            print("❌ No admin found for migration")
            return
            
        admin_id = str(first_admin["_id"])
        
        # Migrate history collection
        history_without_admin = history_collection.count_documents({"admin_id": {"$exists": False}})
        if history_without_admin > 0:
            result = history_collection.update_many(
                {"admin_id": {"$exists": False}},
                {"$set": {"admin_id": admin_id}}
            )
            print(f"✅ Migrated {result.modified_count} history records")
        
        # Migrate temp_collection
        temp_without_admin = temp_collection.count_documents({"admin_id": {"$exists": False}})
        if temp_without_admin > 0:
            result = temp_collection.update_many(
                {"admin_id": {"$exists": False}},
                {"$set": {"admin_id": admin_id}}
            )
            print(f"✅ Migrated {result.modified_count} temp records")
            
        print("✅ Data migration completed")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")

def setup_database():
    """Setup database dengan admin default dan migrasi data"""
    print("🔧 Setting up database...")
    create_default_admin()
    migrate_existing_data()
    print("✅ Database setup completed")

# Jalankan setup saat import
if __name__ == "__main__":
    setup_database()