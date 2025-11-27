import os
import time
import asyncio
import aiohttp
import yt_dlp
import logging
import subprocess
import glob

logger = logging.getLogger(__name__)

class DownloadProgress:
    def __init__(self, index, total, update, bot, user_id):
        self.index = index
        self.total = total
        self.update = update
        self.bot = bot
        self.user_id = user_id
        self.last_update_time = 0
        self.status_msg = None
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.start_time = time.time()
    
    async def create_status_message(self, text):
        try:
            self.status_msg = await self.update.message.reply_text(text)
        except:
            pass
    
    async def update_status(self, downloaded, total):
        self.downloaded_bytes = downloaded
        self.total_bytes = total
        
        current_time = time.time()
        if current_time - self.last_update_time < 2:
            return
        
        self.last_update_time = current_time
        
        try:
            if not self.status_msg:
                return
            
            elapsed = current_time - self.start_time
            speed = downloaded / elapsed if elapsed > 0 else 0
            
            if total > 0:
                percent = (downloaded / total) * 100
                bar_length = 10
                filled = int(bar_length * downloaded / total)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                eta = (total - downloaded) / speed if speed > 0 else 0
                
                text = (
                    f"📥 **Downloading [{self.index}/{self.total}]**\n\n"
                    f"`{bar}` {percent:.1f}%\n\n"
                    f"💾 {self._format_size(downloaded)} / {self._format_size(total)}\n"
                    f"⚡ {self._format_size(speed)}/s\n"
                    f"⏱️ ETA: {self._format_time(eta)}"
                )
            else:
                text = (
                    f"📥 **Downloading [{self.index}/{self.total}]**\n\n"
                    f"💾 {self._format_size(downloaded)}\n"
                    f"⚡ {self._format_size(speed)}/s"
                )
            
            await self.status_msg.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.debug(f"Status update error: {e}")
    
    async def complete(self, success=True):
        try:
            if self.status_msg:
                if success:
                    text = f"✅ **Downloaded [{self.index}/{self.total}]**\n\n💾 {self._format_size(self.downloaded_bytes)}"
                else:
                    text = f"❌ **Download Failed [{self.index}/{self.total}]**"
                await self.status_msg.edit_text(text, parse_mode='Markdown')
        except:
            pass
    
    def _format_size(self, bytes_val):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"
    
    def _format_time(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"

async def download_media(url, media_type, index, total, update, bot, user_id):
    """Main download function"""
    os.makedirs('downloads', exist_ok=True)
    
    progress = DownloadProgress(index, total, update, bot, user_id)
    await progress.create_status_message(f"📥 **Starting download [{index}/{total}]...**")
    
    try:
        timestamp = int(time.time() * 1000)
        output_path = f"downloads/{user_id}_{timestamp}"
        
        if media_type == 'video':
            file_path = await download_video(url, output_path, progress)
        else:
            file_path = await download_pdf(url, output_path, progress)
        
        if file_path and os.path.exists(file_path):
            await progress.complete(success=True)
            logger.info(f"Download successful: {file_path}")
            return file_path
        else:
            await progress.complete(success=False)
            logger.error(f"Download failed: {url}")
            return None
            
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        await progress.complete(success=False)
        return None

async def download_video(url, output_path, progress):
    """Download video using yt-dlp with comprehensive options"""
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            asyncio.create_task(progress.update_status(downloaded, total))
    
    ydl_opts = {
        'outtmpl': output_path + '.%(ext)s',
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': url,
        },
        'socket_timeout': 60,
        'retries': 5,
        'fragment_retries': 10,
        'extractor_retries': 5,
        'file_access_retries': 5,
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash']
            }
        },
        'concurrent_fragment_downloads': 5,
        'external_downloader': 'ffmpeg',
        'external_downloader_args': ['-loglevel', 'error'],
    }
    
    try:
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        await loop.run_in_executor(None, download)
        
        # Find downloaded file
        base_name = os.path.basename(output_path)
        
        # Check for mp4 first
        for pattern in [f"{output_path}.mp4", f"{output_path}*.mp4"]:
            files = glob.glob(pattern)
            if files:
                logger.info(f"Found MP4 file: {files[0]}")
                return files[0]
        
        # Check for any video file
        video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.ts', '.m4v']
        for ext in video_extensions:
            files = glob.glob(f"{output_path}*{ext}")
            if files:
                original_file = files[0]
                logger.info(f"Found video file: {original_file}")
                
                # Convert to mp4 if not already
                if not original_file.endswith('.mp4'):
                    mp4_file = f"{output_path}.mp4"
                    if await convert_to_mp4(original_file, mp4_file):
                        try:
                            os.remove(original_file)
                        except:
                            pass
                        return mp4_file
                
                return original_file
        
        logger.error(f"No video file found for: {url}")
        return None
        
    except Exception as e:
        logger.error(f"Video download error: {e}", exc_info=True)
        return None

async def convert_to_mp4(input_file, output_file):
    """Convert video to mp4 using ffmpeg"""
    try:
        logger.info(f"Converting {input_file} to mp4...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            output_file
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_file):
            logger.info(f"Conversion successful: {output_file}")
            return True
        else:
            logger.error(f"Conversion failed: {stderr.decode()}")
            return False
            
    except Exception as e:
        logger.error(f"Conversion error: {e}", exc_info=True)
        return False

async def download_pdf(url, output_path, progress):
    """Download PDF file"""
    output_file = output_path + '.pdf'
    
    try:
        timeout = aiohttp.ClientTimeout(total=3600, connect=60, sock_read=300)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/pdf,application/octet-stream,*/*',
        }
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output_file, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        await progress.update_status(downloaded, total_size)
        
        if os.path.exists(output_file):
            logger.info(f"PDF downloaded: {output_file}")
            return output_file
        else:
            logger.error(f"PDF file not created: {url}")
            return None
            
    except Exception as e:
        logger.error(f"PDF download error: {e}", exc_info=True)
        return None
