import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from downloader import download_media
from uploader import upload_media
from link_extractor import parse_links
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WAITING_FILE, WAITING_CAPTION = range(2)

# MongoDB
mongo_client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
db = mongo_client['media_bot']

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, format, *args):
        pass

def start_health_server():
    server = HTTPServer(('0.0.0.0', int(os.getenv('PORT', 8000))), HealthHandler)
    server.serve_forever()

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != int(os.getenv('AUTHORIZED_USER_ID')):
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    await update.message.reply_text("📤 Send TXT/HTML file with links")
    return WAITING_FILE

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.endswith(('.txt', '.html', '.htm')):
        await update.message.reply_text("❌ Send TXT or HTML file only")
        return WAITING_FILE
    
    file = await context.bot.get_file(doc.file_id)
    path = f"temp_{update.effective_user.id}.txt"
    await file.download_to_drive(path)
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    os.remove(path)
    
    links = parse_links(content)
    if not links:
        await update.message.reply_text("❌ No links found")
        return ConversationHandler.END
    
    user_data[update.effective_user.id] = {'links': links}
    await update.message.reply_text(f"✅ Found {len(links)} files\n\n💬 Send extra caption or /skip")
    return WAITING_CAPTION

async def handle_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    extra_caption = "" if update.message.text == "/skip" else update.message.text
    
    links = user_data[user_id]['links']
    await update.message.reply_text("🚀 Starting downloads...")
    
    for idx, item in enumerate(links, 1):
        status = await update.message.reply_text(f"📥 [{idx}/{len(links)}] Downloading...")
        
        try:
            file_path = await download_media(item['url'], item['type'], status, context.bot)
            if not file_path:
                await status.edit_text(f"❌ [{idx}/{len(links)}] Download failed")
                continue
            
            caption = f"{item['caption']}\n\n{extra_caption}".strip() if extra_caption else item['caption']
            await status.edit_text(f"📤 [{idx}/{len(links)}] Uploading...")
            
            success = await upload_media(file_path, item['type'], caption, update.effective_chat.id, context.bot, status)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            if success:
                await status.edit_text(f"✅ [{idx}/{len(links)}] Done!")
            else:
                await status.edit_text(f"❌ [{idx}/{len(links)}] Upload failed")
                
        except Exception as e:
            logger.error(f"Error: {e}")
            await status.edit_text(f"❌ [{idx}/{len(links)}] Error")
    
    del user_data[user_id]
    await update.message.reply_text("✅ All done!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled")
    return ConversationHandler.END

def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    
    app = Application.builder().token(os.getenv('BOT_TOKEN')).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WAITING_FILE: [MessageHandler(filters.Document.ALL, handle_file)],
            WAITING_CAPTION: [MessageHandler(filters.TEXT, handle_caption)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(conv)
    
    logger.info("Bot started!")
    app.run_polling()

if __name__ == '__main__':
    main()
