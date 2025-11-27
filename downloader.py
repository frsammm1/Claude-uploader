import os
import time
import asyncio
import aiohttp
import yt_dlp
import logging

logger = logging.getLogger(__name__)

async def download_media(url, media_type, status_msg, bot):
    try:
        os.makedirs('downloads', exist_ok=True)
        output = f"downloads/{int(time.time())}"
        
        if 'm3u8' in url.lower() or media_type == 'video':
            return await download_video(url, output, status_msg, bot)
        else:
            return await download_file(url, output + '.pdf', status_msg, bot)
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

async def download_video(url, output, status_msg, bot):
    try:
        ydl_opts = {
            'outtmpl': output + '.%(ext)s',
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
        }
        
        loop = asyncio.get_event_loop()
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        await loop.run_in_executor(None, download)
        
        # Find downloaded file
        for f in os.listdir('downloads'):
            if f.startswith(os.path.basename(output)):
                return os.path.join('downloads', f)
        
        return None
    except Exception as e:
        logger.error(f"Video download error: {e}")
        return None

async def download_file(url, output, status_msg, bot):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        try:
                            if total > 0:
                                pct = (downloaded / total) * 100
                                await status_msg.edit_text(f"📥 Downloading... {pct:.1f}%")
                        except:
                            pass
        
        return output if os.path.exists(output) else None
    except Exception as e:
        logger.error(f"File download error: {e}")
        return None
