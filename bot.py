import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from downloader import download_media
from uploader import upload_media
from link_parser import extract_all_links
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WAITING_FILE, WAITING_CAPTION = range(2)

try:
    mongo_client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
    db = mongo_client['media_bot']
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    db = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"Health server started on port {port}")
    server.serve_forever()

user_sessions = {}
stop_flags = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    authorized_id = int(os.getenv('AUTHORIZED_USER_ID', 0))
    
    if user_id != authorized_id:
        await update.message.reply_text("❌ You are not authorized to use this bot!")
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        return ConversationHandler.END
    
    stop_flags[user_id] = False
    
    welcome_msg = (
        "🤖 **Media Downloader Bot**\n\n"
        "📤 Send me a TXT or HTML file containing media links\n\n"
        "Supported formats:\n"
        "• Videos (MP4, M3U8, HLS, etc.)\n"
        "• PDFs\n\n"
        "Let's get started!"
    )
    
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    logger.info(f"User {user_id} started the bot")
    return WAITING_FILE

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    
    if not doc.file_name.lower().endswith(('.txt', '.html', '.htm')):
        await update.message.reply_text("❌ Please send only TXT or HTML files!")
        return WAITING_FILE
    
    logger.info(f"User {user_id} uploaded file: {doc.file_name}")
    
    status = await update.message.reply_text("📂 Processing file...")
    
    try:
        file = await context.bot.get_file(doc.file_id)
        temp_path = f"temp_{user_id}_{doc.file_name}"
        await file.download_to_drive(temp_path)
        
        with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        os.remove(temp_path)
        
        logger.info(f"File content length: {len(content)} characters")
        
        links = extract_all_links(content)
        
        if not links:
            await status.edit_text("❌ No valid media links found in the file!")
            logger.warning(f"No links found in file from user {user_id}")
            return ConversationHandler.END
        
        user_sessions[user_id] = {'links': links}
        
        video_count = sum(1 for l in links if l['type'] == 'video')
        pdf_count = sum(1 for l in links if l['type'] == 'pdf')
        
        summary = (
            f"✅ **File Processed Successfully!**\n\n"
            f"📊 Total Links Found: **{len(links)}**\n"
            f"🎥 Videos: **{video_count}**\n"
            f"📄 PDFs: **{pdf_count}**\n\n"
            f"💬 Now send an extra caption to add to all media\n"
            f"or send /skip to use only original captions"
        )
        
        await status.edit_text(summary, parse_mode='Markdown')
        logger.info(f"Found {len(links)} links - Videos: {video_count}, PDFs: {pdf_count}")
        
        return WAITING_CAPTION
        
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        await status.edit_text(f"❌ Error processing file: {str(e)}")
        return ConversationHandler.END

async def handle_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    extra_caption = "" if update.message.text == "/skip" else update.message.text.strip()
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Session expired. Please /start again")
        return ConversationHandler.END
    
    links = user_sessions[user_id]['links']
    stop_flags[user_id] = False
    
    keyboard = [[InlineKeyboardButton("⏹️ STOP ALL", callback_data=f"stop_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    control_msg = await update.message.reply_text(
        "🚀 **Starting batch processing...**\n\nClick STOP to cancel anytime",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    success = 0
    failed = 0
    
    for idx, item in enumerate(links, 1):
        if stop_flags.get(user_id, False):
            await control_msg.edit_text("⏹️ **Process stopped by user**", parse_mode='Markdown')
            logger.info(f"User {user_id} stopped processing at item {idx}")
            break
        
        try:
            caption = f"{item['caption']}\n\n{extra_caption}" if extra_caption else item['caption']
            
            logger.info(f"[{idx}/{len(links)}] Processing: {item['type']} - {item['url'][:100]}")
            
            # Download
            file_path = await download_media(
                url=item['url'],
                media_type=item['type'],
                index=idx,
                total=len(links),
                update=update,
                bot=context.bot,
                user_id=user_id
            )
            
            if not file_path or not os.path.exists(file_path):
                failed += 1
                logger.error(f"[{idx}/{len(links)}] Download failed")
                continue
            
            # Upload
            upload_success = await upload_media(
                file_path=file_path,
                media_type=item['type'],
                caption=caption,
                index=idx,
                total=len(links),
                chat_id=update.effective_chat.id,
                bot=context.bot,
                user_id=user_id
            )
            
            # Cleanup
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
            
            if upload_success:
                success += 1
                logger.info(f"[{idx}/{len(links)}] Successfully processed")
            else:
                failed += 1
                logger.error(f"[{idx}/{len(links)}] Upload failed")
                
        except Exception as e:
            failed += 1
            logger.error(f"[{idx}/{len(links)}] Error: {e}", exc_info=True)
    
    final_summary = (
        f"✅ **Batch Processing Complete!**\n\n"
        f"📊 Statistics:\n"
        f"✓ Success: **{success}**\n"
        f"✗ Failed: **{failed}**\n"
        f"📦 Total: **{len(links)}**\n\n"
        f"Send /start to process another file"
    )
    
    await control_msg.edit_text(final_summary, parse_mode='Markdown')
    logger.info(f"Processing complete - Success: {success}, Failed: {failed}")
    
    # Cleanup
    if user_id in user_sessions:
        del user_sessions[user_id]
    if user_id in stop_flags:
        del stop_flags[user_id]
    
    return ConversationHandler.END

async def stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[1])
    stop_flags[user_id] = True
    
    await query.edit_message_text("⏹️ **Stopping... Please wait**", parse_mode='Markdown')
    logger.info(f"User {user_id} requested stop")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_flags[user_id] = True
    
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    await update.message.reply_text("❌ Operation cancelled. Send /start to begin again")
    logger.info(f"User {user_id} cancelled operation")
    return ConversationHandler.END

def main():
    # Start health check server
    threading.Thread(target=start_health_server, daemon=True).start()
    
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN not found in environment variables!")
        return
    
    app = Application.builder().token(bot_token).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WAITING_FILE: [MessageHandler(filters.Document.ALL, handle_file)],
            WAITING_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_caption)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(stop_callback, pattern='^stop_'))
    
    logger.info("=" * 50)
    logger.info("Bot started successfully!")
    logger.info("Waiting for requests...")
    logger.info("=" * 50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
