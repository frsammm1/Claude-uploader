import os
import time
import asyncio
import aiohttp
import yt_dlp
import logging
import subprocess
import shutil

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
        
        if time.time() - self.last_update < 3:
            return
        
        self.last_update = time.time()
        elapsed = time.time() - self.start_time
        speed = downloaded / elapsed if elapsed > 0 else 0
        
        try:
            pct = (downloaded / total * 100) if total > 0 else 0
            bar = '█' * int(pct/10) + '░' * (10-int(pct/10))
            
            text = (
                f"📥 Downloading...\n\n"
                f"{bar}\n"
                f"📊 {pct:.1f}%\n"
                f"💾 {self.format_size(downloaded)} / {self.format_size(total)}\n"
                f"⚡ {self.format_speed(speed)}"
            )
            
            await self.status_msg.edit_text(text)
        except:
            pass
    
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
        
        logger.info(f"Downloading: {url}")
        
        if media_type == 'video':
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
        
        # Comprehensive yt-dlp options
        ydl_opts = {
            'outtmpl': output + '.%(ext)s',
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
            'geo_bypass': True,
            'nocheckcertificate': True,
            'allow_unplayable_formats': False,
            'fixup': 'detect_or_warn',
            'prefer_ffmpeg': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': url,
            },
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'extractor_retries': 3,
        }
        
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        await loop.run_in_executor(None, download)
        
        # Find downloaded file
        for f in os.listdir('downloads'):
            if f.startswith(os.path.basename(output)) and f.endswith('.mp4'):
                path = os.path.join('downloads', f)
                logger.info(f"Downloaded: {path}")
                return path
        
        # If not mp4, convert
        for f in os.listdir('downloads'):
            if f.startswith(os.path.basename(output)):
                old_path = os.path.join('downloads', f)
                new_path = output + '.mp4'
                
                # Convert to mp4
                logger.info(f"Converting to mp4: {old_path}")
                await convert_to_mp4(old_path, new_path)
                
                if os.path.exists(new_path):
                    os.remove(old_path)
                    return new_path
        
        return None
    except Exception as e:
        logger.error(f"Video download error: {e}")
        return None

async def convert_to_mp4(input_file, output_file):
    """Convert any video to mp4"""
    try:
        cmd = [
            'ffmpeg', '-i', input_file,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-strict', 'experimental',
            '-y', output_file
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        return output_file if os.path.exists(output_file) else None
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return None

async def download_file(url, output, status_msg, bot, user_id):
    try:
        tracker = ProgressTracker(status_msg, bot, user_id)
        
        timeout = aiohttp.ClientTimeout(total=3600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"HTTP {resp.status}")
                    return None
                
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        await tracker.update(downloaded, total)
        
        logger.info(f"Downloaded: {output}")
        return output if os.path.exists(output) else None
    except Exception as e:
        logger.error(f"File download error: {e}")
        return None
