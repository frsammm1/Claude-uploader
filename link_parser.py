import re
from bs4 import BeautifulSoup
import logging
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

def extract_all_links(content):
    """Extract all media links from content (HTML or TXT)"""
    
    links = []
    seen_urls = set()
    
    logger.info("Starting link extraction...")
    
    # Try HTML parsing first
    html_links = extract_from_html(content)
    for link in html_links:
        url = link['url']
        if url not in seen_urls:
            links.append(link)
            seen_urls.add(url)
    
    # Try text parsing
    text_links = extract_from_text(content)
    for link in text_links:
        url = link['url']
        if url not in seen_urls:
            links.append(link)
            seen_urls.add(url)
    
    logger.info(f"Total links extracted: {len(links)}")
    return links

def extract_from_html(content):
    """Extract links from HTML content"""
    
    links = []
    
    try:
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all <a> tags
        for a_tag in soup.find_all('a', href=True):
            url = a_tag['href'].strip()
            caption = a_tag.get_text(strip=True)
            
            # Clean URL
            url = clean_url(url)
            
            if url and is_valid_url(url):
                media_type = detect_media_type(url)
                if media_type:
                    links.append({
                        'url': url,
                        'type': media_type,
                        'caption': caption or 'Media File'
                    })
                    logger.debug(f"HTML: Found {media_type} - {url[:100]}")
    
    except Exception as e:
        logger.debug(f"HTML parsing error: {e}")
    
    return links

def extract_from_text(content):
    """Extract links from plain text"""
    
    links = []
    
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        if not line or len(line) < 10:
            continue
        
        # Extract caption (text before colon or first URL)
        caption = ""
        search_text = line
        
        # Try to find caption before URL
        if ':' in line:
            parts = line.split(':', 1)
            potential_caption = parts[0].strip()
            if len(potential_caption) < 200 and not is_url(potential_caption):
                caption = potential_caption
                search_text = parts[1]
        
        # Find all URLs in the line
        urls = find_all_urls(search_text)
        
        for url in urls:
            url = clean_url(url)
            
            if url and is_valid_url(url):
                media_type = detect_media_type(url)
                if media_type:
                    links.append({
                        'url': url,
                        'type': media_type,
                        'caption': caption or 'Media File'
                    })
                    logger.debug(f"TEXT: Found {media_type} - {url[:100]}")
    
    return links

def find_all_urls(text):
    """Find all URLs in text using multiple patterns"""
    
    urls = []
    
    # Pattern 1: Full URLs with http/https
    pattern1 = r'https?://[^\s<>"\'`|(){}[\]]+[^\s<>"\'`|(){}[\].,;:!?]'
    urls.extend(re.findall(pattern1, text))
    
    # Pattern 2: URLs starting with www
    pattern2 = r'www\.[^\s<>"\'`|(){}[\]]+[^\s<>"\'`|(){}[\].,;:!?]'
    www_urls = re.findall(pattern2, text)
    urls.extend(['https://' + url for url in www_urls])
    
    # Pattern 3: Domain-like patterns
    pattern3 = r'[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}[^\s<>"\'`|(){}[\]]*'
    domain_urls = re.findall(pattern3, text)
    for url in domain_urls:
        if not url.startswith(('http://', 'https://', 'www.')):
            # Check if it looks like a real domain
            if '.' in url and len(url.split('.')[0]) > 2:
                urls.append('https://' + url)
    
    return list(set(urls))

def clean_url(url):
    """Clean and normalize URL"""
    
    # Remove common trailing characters
    url = url.rstrip('.,;:!?)\'"')
    
    # Remove HTML entities
    url = url.replace('&amp;', '&')
    
    # Decode URL encoding
    try:
        url = unquote(url)
    except:
        pass
    
    # Add https if missing
    if url.startswith('www.'):
        url = 'https://' + url
    
    return url.strip()

def is_url(text):
    """Check if text looks like a URL"""
    return text.startswith(('http://', 'https://', 'www.')) or '://' in text

def is_valid_url(url):
    """Validate URL"""
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and len(url) > 15
    except:
        return False

def detect_media_type(url):
    """Detect if URL is video or PDF"""
    
    url_lower = url.lower()
    
    # Video patterns (comprehensive)
    video_patterns = [
        # File extensions
        '.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.m4v',
        '.3gp', '.wmv', '.mpg', '.mpeg', '.m2v', '.ts',
        
        # Streaming formats
        '.m3u8', 'master.m3u8', 'playlist.m3u8', '.m3u',
        
        # Domain/path patterns
        '/hls/', '/video/', '/stream/', '/media/', '/watch/',
        'hranker.com', 'amazonaws.com', 'cloudflare', 'selectionway',
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion',
        'cdn', 'player', '/v/', '/embed/'
    ]
    
    for pattern in video_patterns:
        if pattern in url_lower:
            return 'video'
    
    # PDF patterns
    pdf_patterns = ['.pdf', 'pdf', '/pdfs/', 'document']
    
    for pattern in pdf_patterns:
        if pattern in url_lower:
            return 'pdf'
    
    # Check file extension at end
    if url_lower.endswith(tuple(video_patterns)):
        return 'video'
    
    if url_lower.endswith('.pdf'):
        return 'pdf'
    
    return None
