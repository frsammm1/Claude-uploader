import os
import math
import logging

logger = logging.getLogger(__name__)

MAX_SIZE = 2000 * 1024 * 1024  # 2GB

async def upload_media(file_path, media_type, caption, chat_id, bot, status_msg):
    try:
        size = os.path.getsize(file_path)
        
        if size > MAX_SIZE:
            return await upload_parts(file_path, media_type, caption, chat_id, bot, status_msg)
        else:
            return await upload_single(file_path, media_type, caption, chat_id, bot)
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return False

async def upload_single(file_path, media_type, caption, chat_id, bot):
    try:
        with open(file_path, 'rb') as f:
            if media_type == 'video':
                await bot.send_video(chat_id, f, caption=caption[:1024] if caption else None, supports_streaming=True)
            else:
                await bot.send_document(chat_id, f, caption=caption[:1024] if caption else None)
        return True
    except Exception as e:
        logger.error(f"Single upload error: {e}")
        return False

async def upload_parts(file_path, media_type, caption, chat_id, bot, status_msg):
    try:
        size = os.path.getsize(file_path)
        parts = math.ceil(size / MAX_SIZE)
        
        await status_msg.edit_text(f"📦 Splitting into {parts} parts...")
        
        part_files = split_file(file_path, parts)
        success = 0
        
        for i, pf in enumerate(part_files, 1):
            try:
                await status_msg.edit_text(f"📤 Uploading part {i}/{parts}...")
                cap = f"{caption}\n\n📦 Part {i}/{parts}" if caption else f"📦 Part {i}/{parts}"
                
                with open(pf, 'rb') as f:
                    if media_type == 'video':
                        await bot.send_video(chat_id, f, caption=cap[:1024])
                    else:
                        await bot.send_document(chat_id, f, caption=cap[:1024])
                
                success += 1
                os.remove(pf)
            except Exception as e:
                logger.error(f"Part upload error: {e}")
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
    
    return part_files
