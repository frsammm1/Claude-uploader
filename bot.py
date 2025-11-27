import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from downloader import download_media
from uploader import upload_media_batch
from link_extractor import parse_links
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WAITING_FILE, WAITING_CAPTION = range(2)

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
stop_flags = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != int(os.getenv('AUTHORIZED_USER_ID')):
        await update.message.reply_text("❌ Unauthorized")
        return ConversationHandler.END
    
    stop_flags[user_id] = False
    await update.message.reply_text("📤 Send TXT/HTML file with links")
    return WAITING_FILE

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    
    if not doc.file_name.endswith(('.txt', '.html', '.htm')):
        await update.message.reply_text("❌ Send TXT or HTML file only")
        return WAITING_FILE
    
    logger.info(f"Processing file: {doc.file_name}")
    
    file = await context.bot.get_file(doc.file_id)
    path = f"temp_{user_id}.txt"
    await file.download_to_drive(path)
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    os.remove(path)
    
    links = parse_links(content)
    
    if not links:
        await update.message.reply_text("❌ No links found")
        return ConversationHandler.END
    
    user_data[user_id] = {'links': links}
    
    videos = sum(1 for l in links if l['type'] == 'video')
    pdfs = sum(1 for l in links if l['type'] == 'pdf')
    
    await update.message.reply_text(
        f"✅ Found {len(links)} files!\n"
        f"🎥 Videos: {videos}\n"
        f"📄 PDFs: {pdfs}\n\n"
        f"💬 Send extra caption or /skip"
    )
    
    logger.info(f"Detected {len(links)} links (Videos: {videos}, PDFs: {pdfs})")
    return WAITING_CAPTION

async def handle_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    extra_caption = "" if update.message.text == "/skip" else update.message.text
    
    links = user_data[user_id]['links']
    stop_flags[user_id] = False
    
    keyboard = [[InlineKeyboardButton("⏹️ STOP ALL", callback_data=f"stop_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    control_msg = await update.message.reply_text("🚀 Starting batch processing...", reply_markup=reply_markup)
    
    success_count = 0
    failed_count = 0
    downloaded_files = []
    
    # Download all first
    for idx, item in enumerate(links, 1):
        if stop_flags.get(user_id, False):
            break
        
        status = await update.message.reply_text(f"📥 [{idx}/{len(links)}] Downloading...\n{item['caption'][:50]}")
        
        try:
            logger.info(f"[{idx}/{len(links)}] Downloading: {item['url']}")
            
            file_path = await download_media(item['url'], item['type'], status, context.bot, user_id)
            
            if file_path and os.path.exists(file_path):
                downloaded_files.append({
                    'file': file_path,
                    'type': item['type'],
                    'caption': f"{item['caption']}\n\n{extra_caption}".strip() if extra_caption else item['caption'],
                    'index': idx
                })
                await status.edit_text(f"✅ [{idx}/{len(links)}] Downloaded")
                logger.info(f"[{idx}/{len(links)}] Success: {file_path}")
            else:
                await status.edit_text(f"❌ [{idx}/{len(links)}] Failed")
                failed_count += 1
                logger.error(f"[{idx}/{len(links)}] Download failed")
                
        except Exception as e:
            logger.error(f"[{idx}/{len(links)}] Error: {e}")
            await status.edit_text(f"❌ [{idx}/{len(links)}] Error")
            failed_count += 1
    
    # Upload all in batch
    if downloaded_files and not stop_flags.get(user_id, False):
        await control_msg.edit_text("📤 Uploading all files...")
        
        uploaded = await upload_media_batch(downloaded_files, update.effective_chat.id, context.bot, user_id)
        success_count = uploaded
        failed_count += len(downloaded_files) - uploaded
        
        # Cleanup
        for item in downloaded_files:
            if os.path.exists(item['file']):
                os.remove(item['file'])
    
    summary = (
        f"✅ Complete!\n\n"
        f"📊 Success: {success_count}\n"
        f"❌ Failed: {failed_count}\n"
        f"📦 Total: {len(links)}"
    )
    
    await control_msg.edit_text(summary)
    
    if user_id in user_data:
        del user_data[user_id]
    if user_id in stop_flags:
        del stop_flags[user_id]
    
    logger.info(f"Completed: {success_count} success, {failed_count} failed")
    
    return ConversationHandler.END

async def stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[1])
    stop_flags[user_id] = True
    
    await query.edit_message_text("⏹️ Stopping...")
    logger.info(f"User {user_id} stopped")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_flags[user_id] = True
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
    app.add_handler(CallbackQueryHandler(stop_callback, pattern='^stop_'))
    
    logger.info("Bot started!")
    app.run_polling()

if __name__ == '__main__':
    main()
