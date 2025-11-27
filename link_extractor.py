import re
from bs4 import BeautifulSoup

def parse_links(content):
    links = []
    seen = set()
    
    # Try HTML first
    try:
        soup = BeautifulSoup(content, 'html.parser')
        for a in soup.find_all('a', href=True):
            url = a['href']
            caption = a.get_text(strip=True)
            
            if url not in seen and is_valid_url(url):
                links.append({
                    'url': url,
                    'type': get_type(url),
                    'caption': caption
                })
                seen.add(url)
    except:
        pass
    
    # Text parsing
    if not links:
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Get caption
            caption = ""
            if ':' in line:
                parts = line.split(':', 1)
                caption = parts[0].strip()
                search_text = parts[1]
            else:
                search_text = line
            
            # Find URLs
            urls = re.findall(r'https?://[^\s<>"]+', search_text)
            
            for url in urls:
                url = url.rstrip('.,;:!?)')
                
                if url not in seen and is_valid_url(url):
                    links.append({
                        'url': url,
                        'type': get_type(url),
                        'caption': caption
                    })
                    seen.add(url)
    
    return links

def is_valid_url(url):
    return url.startswith('http') and len(url) > 10

def get_type(url):
    url_lower = url.lower()
    
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.m3u8']
    if any(ext in url_lower for ext in video_exts):
        return 'video'
    
    if '.pdf' in url_lower:
        return 'pdf'
    
    # Check domain patterns
    video_patterns = ['video', 'stream', 'hls', 'master', 'playlist', 'hranker', 'amazonaws']
    if any(p in url_lower for p in video_patterns):
        return 'video'
    
    return 'pdf'
