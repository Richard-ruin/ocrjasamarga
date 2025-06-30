import aiofiles
import aiofiles.os
from pathlib import Path
from typing import Optional, Dict, Any, List
import hashlib
import mimetypes
import uuid
from datetime import datetime
import logging

from app.config import settings
from app.utils.helpers import clean_filename, format_file_size
from app.utils.validators import validate_file_upload

logger = logging.getLogger(__name__)

class FileService:
    """Service untuk handle file operations"""
    
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.images_dir = self.upload_dir / "images"
        self.generated_dir = self.upload_dir / "generated"
        self.temp_dir = self.upload_dir / "temp"
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        for directory in [self.upload_dir, self.images_dir, self.generated_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def save_uploaded_file(
        self, 
        file_content: bytes, 
        filename: str, 
        content_type: str,
        subfolder: str = "images"
    ) -> Dict[str, Any]:
        """
        Save uploaded file to disk
        
        Args:
            file_content: Binary file content
            filename: Original filename
            content_type: MIME type
            subfolder: Subfolder to save in (images, generated, temp)
            
        Returns:
            Dict with file information
        """
        try:
            # Validate file
            validation = validate_file_upload(
                filename=filename,
                content_type=content_type,
                file_size=len(file_content),
                max_size=settings.max_file_size
            )
            
            if not validation["valid"]:
                return {
                    "success": False,
                    "errors": validation["errors"],
                    "message": "File validation failed"
                }
            
            # Generate unique filename
            clean_name = clean_filename(filename)
            unique_filename = f"{uuid.uuid4().hex[:8]}_{clean_name}"
            
            # Determine save path
            save_dir = self.upload_dir / subfolder
            save_dir.mkdir(exist_ok=True)
            file_path = save_dir / unique_filename
            
            # Calculate file hash
            file_hash = hashlib.md5(file_content).hexdigest()
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            # Get file stats
            stat = await aiofiles.os.stat(file_path)
            
            result = {
                "success": True,
                "filename": unique_filename,
                "original_filename": filename,
                "file_path": str(file_path),
                "relative_path": f"/{subfolder}/{unique_filename}",
                "file_size": stat.st_size,
                "content_type": content_type,
                "file_hash": file_hash,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "message": "File saved successfully"
            }
            
            logger.info(f"File saved: {unique_filename} ({format_file_size(stat.st_size)})")
            return result
            
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to save file"
            }
    
    async def delete_file(self, file_path: str) -> Dict[str, Any]:
        """
        Delete file from disk
        
        Args:
            file_path: Path to file (relative or absolute)
            
        Returns:
            Dict with deletion result
        """
        try:
            # Convert to Path object
            if file_path.startswith('/'):
                # Relative path from uploads
                path = self.upload_dir / file_path.lstrip('/')
            else:
                path = Path(file_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "error": "File not found",
                    "file_path": str(path)
                }
            
            # Check if file is within upload directory (security)
            if not str(path.resolve()).startswith(str(self.upload_dir.resolve())):
                return {
                    "success": False,
                    "error": "File path not allowed",
                    "file_path": str(path)
                }
            
            # Delete file
            await aiofiles.os.remove(path)
            
            logger.info(f"File deleted: {path}")
            return {
                "success": True,
                "file_path": str(path),
                "message": "File deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path,
                "message": "Failed to delete file"
            }
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get file information
        
        Args:
            file_path: Path to file
            
        Returns:
            Dict with file information
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    "exists": False,
                    "file_path": file_path,
                    "message": "File not found"
                }
            
            stat = await aiofiles.os.stat(path)
            content_type, _ = mimetypes.guess_type(str(path))
            
            # Calculate file hash if it's a small file
            file_hash = None
            if stat.st_size < 50 * 1024 * 1024:  # Less than 50MB
                async with aiofiles.open(path, 'rb') as f:
                    content = await f.read()
                    file_hash = hashlib.md5(content).hexdigest()
            
            return {
                "exists": True,
                "file_path": str(path),
                "filename": path.name,
                "file_size": stat.st_size,
                "file_size_formatted": format_file_size(stat.st_size),
                "content_type": content_type,
                "file_hash": file_hash,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "message": "File information retrieved"
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return {
                "exists": False,
                "error": str(e),
                "file_path": file_path,
                "message": "Failed to get file information"
            }
    
    async def list_files(self, subfolder: str = "images", limit: int = 100) -> Dict[str, Any]:
        """
        List files in a directory
        
        Args:
            subfolder: Subfolder to list
            limit: Maximum number of files to return
            
        Returns:
            Dict with file list
        """
        try:
            directory = self.upload_dir / subfolder
            
            if not directory.exists():
                return {
                    "success": True,
                    "files": [],
                    "total": 0,
                    "directory": str(directory),
                    "message": "Directory not found"
                }
            
            files = []
            count = 0
            
            for file_path in directory.iterdir():
                if file_path.is_file() and count < limit:
                    stat = await aiofiles.os.stat(file_path)
                    content_type, _ = mimetypes.guess_type(str(file_path))
                    
                    files.append({
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "relative_path": f"/{subfolder}/{file_path.name}",
                        "file_size": stat.st_size,
                        "file_size_formatted": format_file_size(stat.st_size),
                        "content_type": content_type,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    count += 1
            
            # Sort by creation time (newest first)
            files.sort(key=lambda x: x["created_at"], reverse=True)
            
            return {
                "success": True,
                "files": files,
                "total": len(files),
                "directory": str(directory),
                "message": f"Found {len(files)} files"
            }
            
        except Exception as e:
            logger.error(f"Failed to list files in {subfolder}: {e}")
            return {
                "success": False,
                "error": str(e),
                "directory": str(self.upload_dir / subfolder),
                "message": "Failed to list files"
            }
    
    async def cleanup_old_files(self, subfolder: str, days_old: int = 30) -> Dict[str, Any]:
        """
        Clean up files older than specified days
        
        Args:
            subfolder: Subfolder to clean
            days_old: Files older than this will be deleted
            
        Returns:
            Dict with cleanup result
        """
        try:
            directory = self.upload_dir / subfolder
            
            if not directory.exists():
                return {
                    "success": True,
                    "deleted_files": [],
                    "total_deleted": 0,
                    "message": "Directory not found"
                }
            
            cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            deleted_files = []
            total_size_freed = 0
            
            for file_path in directory.iterdir():
                if file_path.is_file():
                    stat = await aiofiles.os.stat(file_path)
                    
                    if stat.st_mtime < cutoff_time:
                        try:
                            total_size_freed += stat.st_size
                            await aiofiles.os.remove(file_path)
                            deleted_files.append({
                                "filename": file_path.name,
                                "file_size": stat.st_size,
                                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                            })
                        except Exception as e:
                            logger.warning(f"Failed to delete old file {file_path}: {e}")
            
            logger.info(f"Cleanup completed: deleted {len(deleted_files)} files, freed {format_file_size(total_size_freed)}")
            
            return {
                "success": True,
                "deleted_files": deleted_files,
                "total_deleted": len(deleted_files),
                "total_size_freed": total_size_freed,
                "total_size_freed_formatted": format_file_size(total_size_freed),
                "cutoff_days": days_old,
                "message": f"Deleted {len(deleted_files)} old files"
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to cleanup old files"
            }
    
    async def move_file(self, source_path: str, dest_subfolder: str) -> Dict[str, Any]:
        """
        Move file from one location to another
        
        Args:
            source_path: Current file path
            dest_subfolder: Destination subfolder
            
        Returns:
            Dict with move result
        """
        try:
            source = Path(source_path)
            dest_dir = self.upload_dir / dest_subfolder
            dest_dir.mkdir(exist_ok=True)
            dest_path = dest_dir / source.name
            
            if not source.exists():
                return {
                    "success": False,
                    "error": "Source file not found",
                    "source_path": str(source)
                }
            
            # Move file
            await aiofiles.os.rename(source, dest_path)
            
            return {
                "success": True,
                "source_path": str(source),
                "dest_path": str(dest_path),
                "relative_path": f"/{dest_subfolder}/{dest_path.name}",
                "message": "File moved successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to move file from {source_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "source_path": source_path,
                "message": "Failed to move file"
            }

# Global file service instance
file_service = FileService()