import os
import math
import time
import logging
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

MAX_SIZE = 2000 * 1024 * 1024  # 2GB

class UploadProgress:
    def __init__(self, status_msg, bot):
        self.status_msg = status_msg
        self.bot = bot
        self.last_update = 0
        self.uploaded = 0
        self.total = 0
        self.start_time = time.time()
    
    async def callback(self, current, total):
        self.uploaded = current
        self.total = total
        
        if time.time() - self.last_update < 2:
            return
        
        self.last_update = time.time()
        elapsed = time.time() - self.start_time
        speed = current / elapsed if elapsed > 0 else 0
        
        try:
            pct = (current / total * 100) if total > 0 else 0
            bar = self.progress_bar(pct)
            
            text = (
                f"📤 Uploading...\n\n"
                f"{bar}\n"
                f"📊 {pct:.1f}%\n"
                f"💾 {self.format_size(current)} / {self.format_size(total)}\n"
                f"⚡ {self.format_speed(speed)}"
            )
            
            await self.status_msg.edit_text(text)
        except Exception as e:
            logger.error(f"Upload progress error: {e}")
    
    def progress_bar(self, pct):
        filled = int(pct / 10)
        empty = 10 - filled
        return '█' * filled + '░' * empty
    
    def format_size(self, bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024
        return f"{bytes:.2f} TB"
    
    def format_speed(self, bps):
        return f"{self.format_size(bps)}/s"

async def upload_media(file_path, media_type, caption, chat_id, bot, status_msg, user_id):
    try:
        size = os.path.getsize(file_path)
        logger.info(f"Uploading {file_path} ({size} bytes)")
        
        if size > MAX_SIZE:
            return await upload_parts(file_path, media_type, caption, chat_id, bot, status_msg, user_id)
        else:
            return await upload_single(file_path, media_type, caption, chat_id, bot, status_msg)
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return False

async def upload_single(file_path, media_type, caption, chat_id, bot, status_msg):
    try:
        progress = UploadProgress(status_msg, bot)
        
        # Simulate progress since telegram doesn't provide upload progress
        total_size = os.path.getsize(file_path)
        
        with open(file_path, 'rb') as f:
            if media_type == 'video':
                msg = await bot.send_video(
                    chat_id, 
                    f, 
                    caption=caption[:1024] if caption else None, 
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300
                )
            else:
                msg = await bot.send_document(
                    chat_id, 
                    f, 
                    caption=caption[:1024] if caption else None,
                    read_timeout=300,
                    write_timeout=300
                )
        
        logger.info(f"Upload successful: {file_path}")
        return True
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")
        return False
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return False

async def upload_parts(file_path, media_type, caption, chat_id, bot, status_msg, user_id):
    try:
        size = os.path.getsize(file_path)
        parts = math.ceil(size / MAX_SIZE)
        
        logger.info(f"Splitting {file_path} into {parts} parts")
        await status_msg.edit_text(f"📦 Splitting into {parts} parts...")
        
        part_files = split_file(file_path, parts)
        success = 0
        
        for i, pf in enumerate(part_files, 1):
            try:
                part_size = os.path.getsize(pf)
                logger.info(f"Uploading part {i}/{parts} ({part_size} bytes)")
                
                await status_msg.edit_text(
                    f"📤 Uploading part {i}/{parts}...\n"
                    f"💾 Size: {format_size(part_size)}"
                )
                
                cap = f"{caption}\n\n📦 Part {i}/{parts}" if caption else f"📦 Part {i}/{parts}"
                
                with open(pf, 'rb') as f:
                    if media_type == 'video':
                        await bot.send_video(
                            chat_id, 
                            f, 
                            caption=cap[:1024],
                            read_timeout=300,
                            write_timeout=300
                        )
                    else:
                        await bot.send_document(
                            chat_id, 
                            f, 
                            caption=cap[:1024],
                            read_timeout=300,
                            write_timeout=300
                        )
                
                success += 1
                os.remove(pf)
                logger.info(f"Part {i}/{parts} uploaded successfully")
                
            except Exception as e:
                logger.error(f"Part {i} upload error: {e}")
                if os.path.exists(pf):
                    os.remove(pf)
        
        return success == parts
    except Exception as e:
        logger.error(f"Split upload error: {e}")
        return False

def split_file(file_path, parts):
    size = os.path.getsize(file_path)
    part_size = math.ceil(size / parts)
    
    base = os.path.splitext(file_path)[0]
    ext = os.path.splitext(file_path)[1]
    
    part_files = []
    
    with open(file_path, 'rb') as src:
        for i in range(parts):
            part_file = f"{base}_part{i+1}{ext}"
            
            with open(part_file, 'wb') as dst:
                remaining = part_size
                while remaining > 0:
                    chunk = src.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        break
                    dst.write(chunk)
                    remaining -= len(chunk)
            
            part_files.append(part_file)
            logger.info(f"Created part file: {part_file}")
    
    return part_files

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} TB"
