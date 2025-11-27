import re
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_links(content):
    """Parse all video and PDF links from content"""
    links = []
    seen = set()
    
    # Try HTML parsing first
    try:
        soup = BeautifulSoup(content, 'html.parser')
        for a in soup.find_all('a', href=True):
            url = a['href'].strip()
            caption = a.get_text(strip=True)
            
            if url and url not in seen and is_valid_url(url):
                link_type = get_type(url)
                if link_type:
                    links.append({
                        'url': url,
                        'type': link_type,
                        'caption': caption or 'No title'
                    })
                    seen.add(url)
                    logger.info(f"Found link: {caption} - {url}")
    except Exception as e:
        logger.error(f"HTML parsing error: {e}")
    
    # Text parsing - more aggressive
    if not links:
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            # Extract caption
            caption = ""
            search_text = line
            
            if ':' in line:
                parts = line.split(':', 1)
                caption = parts[0].strip()
                search_text = parts[1]
            elif '|' in line:
                parts = line.split('|', 1)
                caption = parts[0].strip()
                search_text = parts[1]
            
            # Find all URLs - more patterns
            url_patterns = [
                r'https?://[^\s<>"]+',
                r'www\.[^\s<>"]+',
            ]
            
            urls = []
            for pattern in url_patterns:
                found = re.findall(pattern, search_text)
                urls.extend(found)
            
            for url in urls:
                # Clean URL
                url = url.rstrip('.,;:!?)\'"')
                url = url.split()[0]  # Take first part if space
                
                # Add http if missing
                if url.startswith('www.'):
                    url = 'https://' + url
                
                if url and url not in seen and is_valid_url(url):
                    link_type = get_type(url)
                    if link_type:
                        links.append({
                            'url': url,
                            'type': link_type,
                            'caption': caption or 'No title'
                        })
                        seen.add(url)
                        logger.info(f"Found link: {caption} - {url}")
    
    logger.info(f"Total links parsed: {len(links)}")
    return links

def is_valid_url(url):
    """Check if URL is valid"""
    if not url or len(url) < 10:
        return False
    
    if not (url.startswith('http://') or url.startswith('https://')):
        return False
    
    # Check for common patterns
    invalid_patterns = ['javascript:', 'mailto:', 'tel:', '#', 'data:']
    for pattern in invalid_patterns:
        if pattern in url.lower():
            return False
    
    return True

def get_type(url):
    """Determine if URL is video or PDF"""
    url_lower = url.lower()
    
    # Video extensions
    video_exts = [
        '.mp4', '.mkv', '.avi', '.mov', '.flv', 
        '.webm', '.m3u8', '.ts', '.3gp', '.wmv'
    ]
    
    for ext in video_exts:
        if ext in url_lower:
            return 'video'
    
    # PDF
    if '.pdf' in url_lower:
        return 'pdf'
    
    # Domain and path patterns for videos
    video_indicators = [
        'video', 'stream', 'hls', 'master', 'playlist',
        'hranker', 'amazonaws', 'cloudflare', 'cdn',
        'mp4', 'mkv', 'watch', 'play', 'embed',
        '/v/', '/videos/', '/media/'
    ]
    
    for indicator in video_indicators:
        if indicator in url_lower:
            return 'video'
    
    # PDF indicators
    pdf_indicators = ['pdf', 'document', 'docs', 'files']
    for indicator in pdf_indicators:
        if indicator in url_lower:
            return 'pdf'
    
    # Default to video for media platforms
    media_domains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
        'streamable.com', 'vidyard.com', 'wistia.com', 'brightcove.com',
        'jwplayer.com', 'cloudflare.com', 'amazonaws.com', 'hranker.com'
    ]
    
    for domain in media_domains:
        if domain in url_lower:
            return 'video'
    
    return None
