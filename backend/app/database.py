from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    database = None

db = Database()

async def get_database():
    """Get database instance"""
    return db.database

async def connect_to_mongo():
    """Create database connection"""
    logger.info("Connecting to MongoDB...")
    try:
        db.client = AsyncIOMotorClient(settings.mongodb_url)
        db.database = db.client[settings.database_name]
        
        # Test connection
        await db.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
        # Create indexes
        await create_indexes()
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e

async def close_mongo_connection():
    """Close database connection"""
    logger.info("Closing MongoDB connection...")
    if db.client:
        db.client.close()

async def create_indexes():
    """Create database indexes for better performance"""
    try:
        # Users collection indexes
        await db.database.users.create_index("email", unique=True)
        await db.database.users.create_index("username", unique=True)
        
        # Jadwal collection indexes
        await db.database.jadwal.create_index("user_id")
        await db.database.jadwal.create_index("waktu")
        
        # Inspeksi collection indexes
        await db.database.inspeksi.create_index("user_id")
        await db.database.inspeksi.create_index("jadwal_id")
        await db.database.inspeksi.create_index("created_at")
        
        # History collection indexes
        await db.database.history.create_index("user_id")
        await db.database.history.create_index("inspeksi_id")
        await db.database.history.create_index("created_at")
        
        # Cache collection indexes with TTL
        await db.database.cache.create_index("expires_at", expireAfterSeconds=0)
        await db.database.cache.create_index("user_id")
        await db.database.cache.create_index("session_id")
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        raise e