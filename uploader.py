import os
import math
import logging
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

MAX_SIZE = 2000 * 1024 * 1024  # 2GB

async def upload_media_batch(files_list, chat_id, bot, user_id):
    """Upload all files in one go"""
    success = 0
    
    for item in files_list:
        try:
            file_path = item['file']
            media_type = item['type']
            caption = item['caption']
            
            size = os.path.getsize(file_path)
            logger.info(f"Uploading: {file_path} ({format_size(size)})")
            
            if size > MAX_SIZE:
                # Split large files
                parts = math.ceil(size / MAX_SIZE)
                part_files = split_file(file_path, parts)
                
                for i, pf in enumerate(part_files, 1):
                    cap = f"{caption}\n\n📦 Part {i}/{parts}"
                    await upload_single(pf, media_type, cap, chat_id, bot)
                    os.remove(pf)
                
                success += 1
            else:
                # Upload single
                if await upload_single(file_path, media_type, caption, chat_id, bot):
                    success += 1
                    
        except Exception as e:
            logger.error(f"Upload error: {e}")
    
    return success

async def upload_single(file_path, media_type, caption, chat_id, bot):
    try:
        with open(file_path, 'rb') as f:
            if media_type == 'video':
                await bot.send_video(
                    chat_id, 
                    f, 
                    caption=caption[:1024] if caption else None, 
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60
                )
            else:
                await bot.send_document(
                    chat_id, 
                    f, 
                    caption=caption[:1024] if caption else None,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60
                )
        
        logger.info(f"Uploaded: {file_path}")
        return True
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")
        return False
    except Exception as e:
        logger.error(f"Upload error: {e}")
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
    
    return part_files

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024
    return f"{bytes:.2f} TB"
