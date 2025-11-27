import os
import math
import logging
import asyncio
from telegram.error import TelegramError, NetworkError, TimedOut

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2GB Telegram limit

class UploadProgress:
    def __init__(self, index, total, chat_id, bot):
        self.index = index
        self.total = total
        self.chat_id = chat_id
        self.bot = bot
        self.status_msg = None
    
    async def create_status(self):
        try:
            self.status_msg = await self.bot.send_message(
                self.chat_id,
                f"📤 **Uploading [{self.index}/{self.total}]...**",
                parse_mode='Markdown'
            )
        except:
            pass
    
    async def update(self, current, total, part=None):
        try:
            if not self.status_msg:
                return
            
            percent = (current / total * 100) if total > 0 else 0
            bar_length = 10
            filled = int(bar_length * current / total) if total > 0 else 0
            bar = '█' * filled + '░' * (bar_length - filled)
            
            part_text = f" (Part {part})" if part else ""
            
            text = (
                f"📤 **Uploading [{self.index}/{self.total}]{part_text}**\n\n"
                f"`{bar}` {percent:.1f}%\n\n"
                f"💾 {self._format_size(current)} / {self._format_size(total)}"
            )
            
            await self.status_msg.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.debug(f"Upload status update error: {e}")
    
    async def complete(self, success=True, part=None):
        try:
            if self.status_msg:
                part_text = f" (Part {part})" if part else ""
                if success:
                    text = f"✅ **Uploaded [{self.index}/{self.total}]{part_text}**"
                else:
                    text = f"❌ **Upload Failed [{self.index}/{self.total}]{part_text}**"
                await self.status_msg.edit_text(text, parse_mode='Markdown')
        except:
            pass
    
    def _format_size(self, bytes_val):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"

async def upload_media(file_path, media_type, caption, index, total, chat_id, bot, user_id):
    """Main upload function with file splitting for large files"""
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    file_size = os.path.getsize(file_path)
    logger.info(f"Uploading {file_path} ({_format_bytes(file_size)})")
    
    progress = UploadProgress(index, total, chat_id, bot)
    await progress.create_status()
    
    try:
        if file_size > MAX_FILE_SIZE:
            # Split and upload
            logger.info(f"File too large ({_format_bytes(file_size)}), splitting...")
            return await upload_large_file(file_path, media_type, caption, progress, chat_id, bot)
        else:
            # Direct upload
            return await upload_single_file(file_path, media_type, caption, progress, chat_id, bot)
            
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        await progress.complete(success=False)
        return False

async def upload_single_file(file_path, media_type, caption, progress, chat_id, bot, part_num=None):
    """Upload a single file"""
    
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            file_size = os.path.getsize(file_path)
            
            # Limit caption to 1024 characters
            final_caption = caption[:1024] if caption else None
            
            with open(file_path, 'rb') as f:
                if media_type == 'video':
                    # Upload as video
                    await bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=final_caption,
                        supports_streaming=True,
                        read_timeout=600,
                        write_timeout=600,
                        connect_timeout=120,
                        pool_timeout=120
                    )
                else:
                    # Upload as document (PDF)
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=final_caption,
                        read_timeout=600,
                        write_timeout=600,
                        connect_timeout=120,
                        pool_timeout=120
                    )
            
            await progress.complete(success=True, part=part_num)
            logger.info(f"Upload successful: {file_path}")
            return True
            
        except (NetworkError, TimedOut) as e:
            logger.warning(f"Network error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            else:
                logger.error(f"Upload failed after {max_retries} attempts")
                await progress.complete(success=False, part=part_num)
                return False
                
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            await progress.complete(success=False, part=part_num)
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await progress.complete(success=False, part=part_num)
            return False
    
    return False

async def upload_large_file(file_path, media_type, caption, progress, chat_id, bot):
    """Split and upload large files"""
    
    try:
        file_size = os.path.getsize(file_path)
        num_parts = math.ceil(file_size / MAX_FILE_SIZE)
        
        logger.info(f"Splitting into {num_parts} parts...")
        
        part_files = split_file(file_path, num_parts)
        
        if not part_files:
            logger.error("File splitting failed")
            await progress.complete(success=False)
            return False
        
        # Upload each part
        success_count = 0
        
        for i, part_file in enumerate(part_files, 1):
            try:
                part_caption = f"{caption}\n\n📦 Part {i}/{num_parts}"
                
                # Create new progress for this part
                part_progress = UploadProgress(progress.index, progress.total, chat_id, bot)
                await part_progress.create_status()
                
                if await upload_single_file(part_file, media_type, part_caption, part_progress, chat_id, bot, part_num=i):
                    success_count += 1
                
                # Cleanup part file
                try:
                    os.remove(part_file)
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Error uploading part {i}: {e}")
        
        await progress.complete(success=(success_count == num_parts))
        return success_count == num_parts
        
    except Exception as e:
        logger.error(f"Large file upload error: {e}", exc_info=True)
        await progress.complete(success=False)
        return False

def split_file(file_path, num_parts):
    """Split file into multiple parts"""
    
    try:
        file_size = os.path.getsize(file_path)
        part_size = math.ceil(file_size / num_parts)
        
        base_name = os.path.splitext(file_path)[0]
        extension = os.path.splitext(file_path)[1]
        
        part_files = []
        
        with open(file_path, 'rb') as src:
            for i in range(num_parts):
                part_file = f"{base_name}_part{i+1}{extension}"
                
                with open(part_file, 'wb') as dst:
                    remaining = part_size
                    while remaining > 0:
                        chunk_size = min(remaining, 1024 * 1024)  # 1MB chunks
                        chunk = src.read(chunk_size)
                        if not chunk:
                            break
                        dst.write(chunk)
                        remaining -= len(chunk)
                
                if os.path.exists(part_file):
                    part_files.append(part_file)
                    logger.info(f"Created part {i+1}/{num_parts}: {_format_bytes(os.path.getsize(part_file))}")
        
        return part_files
        
    except Exception as e:
        logger.error(f"File splitting error: {e}", exc_info=True)
        return []

def _format_bytes(bytes_val):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"
