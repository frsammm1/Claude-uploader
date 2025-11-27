import os
import time
import asyncio
import aiohttp
import yt_dlp
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ProgressTracker:
    def __init__(self, status_msg, bot, user_id):
        self.status_msg = status_msg
        self.bot = bot
        self.user_id = user_id
        self.last_update = 0
        self.downloaded = 0
        self.total = 0
        self.start_time = time.time()
        
    async def update(self, downloaded, total):
        self.downloaded = downloaded
        self.total = total
        
        if time.time() - self.last_update < 2:
            return
        
        self.last_update = time.time()
        elapsed = time.time() - self.start_time
        speed = downloaded / elapsed if elapsed > 0 else 0
        
        try:
            pct = (downloaded / total * 100) if total > 0 else 0
            speed_str = self.format_speed(speed)
            size_str = f"{self.format_size(downloaded)} / {self.format_size(total)}"
            
            bar = self.progress_bar(pct)
            
            text = (
                f"📥 Downloading...\n\n"
                f"{bar}\n"
                f"📊 {pct:.1f}%\n"
                f"💾 {size_str}\n"
                f"⚡ {speed_str}"
            )
            
            await self.status_msg.edit_text(text)
        except Exception as e:
            logger.error(f"Progress update error: {e}")
    
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

async def download_media(url, media_type, status_msg, bot, user_id):
    try:
        os.makedirs('downloads', exist_ok=True)
        output = f"downloads/{user_id}_{int(time.time())}"
        
        logger.info(f"Starting download: {url}")
        
        if 'm3u8' in url.lower() or media_type == 'video':
            return await download_video(url, output, status_msg, bot, user_id)
        else:
            return await download_file(url, output + '.pdf', status_msg, bot, user_id)
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

async def download_video(url, output, status_msg, bot, user_id):
    try:
        tracker = ProgressTracker(status_msg, bot, user_id)
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                asyncio.create_task(tracker.update(downloaded, total))
        
        ydl_opts = {
            'outtmpl': output + '.%(ext)s',
            'format': 'best[ext=mp4]/best',
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
            'geo_bypass': True,
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info
        
        await loop.run_in_executor(None, download)
        
        for f in os.listdir('downloads'):
            if f.startswith(os.path.basename(output)):
                path = os.path.join('downloads', f)
                logger.info(f"Video downloaded: {path} ({tracker.format_size(os.path.getsize(path))})")
                return path
        
        return None
    except Exception as e:
        logger.error(f"Video download error: {e}")
        return None

async def download_file(url, output, status_msg, bot, user_id):
    try:
        tracker = ProgressTracker(status_msg, bot, user_id)
        
        timeout = aiohttp.ClientTimeout(total=3600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"HTTP {resp.status} for {url}")
                    return None
                
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        await tracker.update(downloaded, total)
        
        logger.info(f"File downloaded: {output} ({tracker.format_size(os.path.getsize(output))})")
        return output if os.path.exists(output) else None
    except Exception as e:
        logger.error(f"File download error: {e}")
        return None
