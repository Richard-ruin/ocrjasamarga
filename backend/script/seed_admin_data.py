# simple_seed.py - Script sederhana untuk seed data admin dan petugas
import asyncio
import os
from datetime import datetime
from config import db  # Import dari config Anda
import bcrypt

def hash_password(password: str) -> str:
    """Hash password menggunakan bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

async def seed_admin_data():
    """Seed data admin dan petugas"""
    admin_collection = db["admins"]
    
    print("🚀 Starting seed process...")
    
    # Data untuk Super Admin
    admin_data = {
        "username": "admin",
        "email": "admin@company.com",
        "password": hash_password("admin123"),
        "full_name": "Super Administrator",
        "role": "admin",
        "is_active": True,
        "created_at": datetime.utcnow(),
        "last_login": None
    }
    
    # Data untuk Petugas
    petugas_data = [
        {
            "username": "petugas1",
            "email": "petugas1@company.com",
            "password": hash_password("petugas123"),
            "full_name": "Budi Santoso",
            "role": "petugas",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None
        },
        {
            "username": "petugas2",
            "email": "petugas2@company.com",
            "password": hash_password("petugas123"),
            "full_name": "Siti Nurhaliza",
            "role": "petugas",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None
        },
        {
            "username": "petugas3",
            "email": "petugas3@company.com",
            "password": hash_password("petugas123"),
            "full_name": "Ahmad Wijaya",
            "role": "petugas",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None
        },
        {
            "username": "operator1",
            "email": "operator1@company.com",
            "password": hash_password("operator123"),
            "full_name": "Lisa Permata",
            "role": "petugas",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": None
        },
        {
            "username": "staff1",
            "email": "staff1@company.com",
            "password": hash_password("staff123"),
            "full_name": "Dedi Kurniawan",
            "role": "petugas",
            "is_active": False,  # Contoh user non-aktif
            "created_at": datetime.utcnow(),
            "last_login": None
        }
    ]
    
    try:
        # Insert Super Admin
        existing_admin = admin_collection.find_one({"username": "admin"})
        if not existing_admin:
            result = admin_collection.insert_one(admin_data)
            if result.inserted_id:
                print("✅ Super Admin created successfully!")
                print(f"   Username: admin")
                print(f"   Password: admin123")
                print(f"   Email: admin@company.com")
            else:
                print("❌ Failed to create Super Admin")
        else:
            print("⚠️  Super Admin already exists")
        
        # Insert Petugas
        print("\n🔄 Creating Petugas accounts...")
        success_count = 0
        
        for petugas in petugas_data:
            existing_user = admin_collection.find_one({
                "$or": [
                    {"username": petugas["username"]},
                    {"email": petugas["email"]}
                ]
            })
            
            if not existing_user:
                result = admin_collection.insert_one(petugas)
                if result.inserted_id:
                    status = "Active" if petugas["is_active"] else "Inactive"
                    print(f"✅ {petugas['full_name']} created ({status})")
                    print(f"   Username: {petugas['username']}")
                    print(f"   Email: {petugas['email']}")
                    success_count += 1
                else:
                    print(f"❌ Failed to create {petugas['full_name']}")
            else:
                print(f"⚠️  {petugas['username']} already exists")
        
        # Summary
        print(f"\n📊 Seed Summary:")
        total_admins = admin_collection.count_documents({"role": "admin"})
        total_petugas = admin_collection.count_documents({"role": "petugas"})
        total_active = admin_collection.count_documents({"is_active": True})
        total_inactive = admin_collection.count_documents({"is_active": False})
        
        print(f"   Total Admin: {total_admins}")
        print(f"   Total Petugas: {total_petugas}")
        print(f"   Total Active Users: {total_active}")
        print(f"   Total Inactive Users: {total_inactive}")
        print(f"   New Users Created: {success_count}")
        
        print("\n🎉 Seed process completed!")
        
        # Default credentials info
        print("\n🔑 Default Login Credentials:")
        print("=" * 40)
        print("SUPER ADMIN:")
        print("  Username: admin")
        print("  Password: admin123")
        print("  Role: admin")
        print("\nPETUGAS:")
        print("  Username: petugas1, petugas2, petugas3, operator1")
        print("  Password: petugas123 (petugas1-3), operator123 (operator1)")
        print("  Role: petugas")
        print("\nINACTIVE USER (for testing):")
        print("  Username: staff1")
        print("  Password: staff123")
        print("  Status: Inactive")
        
    except Exception as e:
        print(f"❌ Error during seed process: {str(e)}")

if __name__ == "__main__":
    # Run seed function
    asyncio.run(seed_admin_data())