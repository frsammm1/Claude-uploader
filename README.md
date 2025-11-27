# Telegram Media Bot

Downloads videos/PDFs from links and uploads to Telegram.

## Setup

1. Copy `.env.example` to `.env`
2. Fill credentials in `.env`
3. Deploy on Render.com
4. Setup cron job at cron-job.org to ping your app every 14 mins

## Files

- `bot.py` - Main bot
- `downloader.py` - Download handler  
- `uploader.py` - Upload with splitting
- `link_parser.py` - Parse links from files
- `requirements.txt` - Dependencies
- `Dockerfile` - Docker config
- `.env.example` - Environment template

## Usage

1. Send `/start`
2. Upload TXT/HTML file with links
3. Add caption or `/skip`
4. Wait for downloads/uploads

## Deploy

Push to GitHub → Render.com → Add env vars → Deploy
