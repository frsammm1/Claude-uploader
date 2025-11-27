import re
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_links(content):
    links = []
    seen = set()
    
    # HTML parsing
    try:
        soup = BeautifulSoup(content, 'html.parser')
        for a in soup.find_all('a', href=True):
            url = a['href'].strip()
            caption = a.get_text(strip=True)
            
            if url and url not in seen:
                link_type = get_type(url)
                if link_type:
                    links.append({'url': url, 'type': link_type, 'caption': caption or 'Media'})
                    seen.add(url)
    except:
        pass
    
    # Text parsing - aggressive
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 15:
            continue
        
        caption = ""
        search_text = line
        
        # Extract caption before first URL
        if ':' in line:
            parts = line.split(':', 1)
            caption = parts[0].strip()
            search_text = parts[1]
        
        # Find ALL URLs - multiple patterns
        urls = []
        urls.extend(re.findall(r'https?://[^\s<>"]+', search_text))
        urls.extend(re.findall(r'www\.[^\s<>"]+', search_text))
        
        for url in urls:
            url = url.rstrip('.,;:!?)\'"')
            if url.startswith('www.'):
                url = 'https://' + url
            
            if url and url not in seen and len(url) > 15:
                link_type = get_type(url)
                if link_type:
                    links.append({'url': url, 'type': link_type, 'caption': caption or 'Media'})
                    seen.add(url)
                    logger.info(f"Found: {url}")
    
    logger.info(f"Total parsed: {len(links)}")
    return links

def get_type(url):
    url_lower = url.lower()
    
    # Video patterns
    video_patterns = [
        '.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.m3u8', 
        '.ts', '.3gp', '.wmv', 'master.m3u8', 'playlist.m3u8',
        '/hls/', '/video/', '/stream/', '/media/', 'hranker.com',
        'amazonaws.com', 'cloudflare', 'selectionway'
    ]
    
    for pattern in video_patterns:
        if pattern in url_lower:
            return 'video'
    
    # PDF
    if '.pdf' in url_lower or 'pdf' in url_lower:
        return 'pdf'
    
    return None
