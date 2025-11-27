# Telegram Media Downloader Bot

A powerful Telegram bot that downloads videos (including M3U8/HLS streams) and PDFs from links in TXT/HTML files and uploads them to your Telegram chat.

## Features

- 📥 **Bulk Download**: Process hundreds of links from a single file
- 🎥 **Video Support**: MP4, M3U8, HLS, and all major video formats
- 📄 **PDF Support**: Direct PDF downloads
- 🔄 **Smart Conversion**: Auto-converts all videos to MP4
- 📊 **Progress Tracking**: Real-time download/upload progress with speed
- ✂️ **File Splitting**: Automatically splits files larger than 2GB
- ⏹️ **Stop Control**: Cancel processing anytime
- 🔐 **Secure**: Only authorized users can use the bot
- 📝 **Custom Captions**: Add extra captions to all media

## Setup Instructions

### 1. Get Your Credentials

**Telegram Bot Token:**
- Go to [@BotFather](https://t.me/BotFather) on Telegram
- Send `/newbot` and follow instructions
- Copy your bot token

**Telegram API Credentials:**
- Go to [my.telegram.org](https://my.telegram.org)
- Login and go to "API development tools"
- Copy your API ID and API Hash

**Your User ID:**
- Send any message to [@userinfobot](https://t.me/userinfobot)
- Copy your user ID

**MongoDB URI:**
- Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
- Create a free cluster (512MB)
- Get connection string (looks like: `mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/?appName=Cluster0`)

### 2. Deploy on Render

1. **Create GitHub Repository:**
   - Create new repo on GitHub
   - Upload all bot files

2. **Deploy on Render:**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Configure:
     - **Name**: `telegram-bot`
     - **Environment**: `Docker`
     - **Plan**: `Free`

3. **Add Environment Variables:**
   ```
   BOT_TOKEN=your_bot_token_here
   TELEGRAM_API_ID=your_api_id_here
   TELEGRAM_API_HASH=your_api_hash_here
   AUTHORIZED_USER_ID=your_user_id_here
   MONGODB_URI=your_mongodb_uri_here
   PORT=8000
   ```

4. **Deploy!**

### 3. Keep Bot Alive (Cron Job)

1. Go to [cron-job.org](https://cron-job.org)
2. Create free account
3. Create new cron job:
   - **URL**: `https://your-app-name.onrender.com/`
   - **Interval**: Every 14 minutes
4. Save and enable

## Usage

1. **Start the bot:**
   ```
   /start
   ```

2. **Upload your file:**
   - Send a TXT or HTML file containing media links
   - Each link should be on a new line
   - Format: `Caption: https://link-to-media`

3. **Add extra caption:**
   - Type your extra caption (added to all media)
   - Or send `/skip` to use only original captions

4. **Wait for processing:**
   - Bot will download and upload all media
   - You can click "STOP ALL" to cancel anytime

## File Format Examples

**TXT Format:**
```
English Class 1: https://example.com/video1.mp4
English Class 2: https://example.com/video2.m3u8
Notes PDF: https://example.com/notes.pdf
```

**HTML Format:**
```html
<a href="https://example.com/video1.mp4">English Class 1</a>
<a href="https://example.com/notes.pdf">Notes PDF</a>
```

## Project Structure

```
telegram-bot/
├── bot.py              # Main bot logic
├── downloader.py       # Download handler with progress
├── uploader.py         # Upload handler with splitting
├── link_parser.py      # Link extraction from files
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker configuration
├── .env.example        # Environment template
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Troubleshooting

**Bot not responding:**
- Check if Render service is running
- Check environment variables are set correctly
- Check bot token is valid

**Downloads failing:**
- Some sites may block automated downloads
- M3U8 links require proper ffmpeg (included in Docker)
- Check logs on Render dashboard

**Uploads failing:**
- Check file size (splits automatically if >2GB)
- Check internet connection
- Telegram has rate limits, bot will retry

## Commands

- `/start` - Start the bot
- `/cancel` - Cancel current operation
- `/skip` - Skip adding extra caption

## Logs

Check logs on Render dashboard:
- Real-time download progress
- Upload status
- Error messages
- Processing statistics

## Notes

- Bot only works for authorized user (set in AUTHORIZED_USER_ID)
- Maximum file size: 2GB per part (auto-splits larger files)
- Videos are automatically converted to MP4
- M3U8/HLS streams are properly handled
- Free Render tier sleeps after 15 min inactivity (cron job keeps it alive)

## Support

For issues:
1. Check logs on Render dashboard
2. Verify all environment variables
3. Test with a small file first
4. Check MongoDB connection

## License

Free to use and modify. No warranty provided.

---

**Made with ❤️ for easy media downloading**
