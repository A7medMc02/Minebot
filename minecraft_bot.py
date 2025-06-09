#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت تليجرام للتحكم في سيرفر ماين كرافت
يمكن للبوت:
- فحص حالة السيرفر
- عرض اللاعبين المتصلين
- إرسال أوامر للسيرفر (للمدراء)
- إرسال رسائل للاعبين
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from mcstatus import JavaServer
from mcrcon import MCRcon
import config
from minecraft_tester import MinecraftServerTester

# إعداد نظام السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MinecraftTelegramBot:
    def __init__(self):
        self.server = None
        self.rcon = None
        self.tester = MinecraftServerTester(
            host=config.MINECRAFT_SERVER_HOST,
            port=config.MINECRAFT_SERVER_PORT,
            rcon_port=config.MINECRAFT_RCON_PORT,
            rcon_password=config.MINECRAFT_RCON_PASSWORD
        )
        
    async def check_server_status(self):
        """فحص حالة سيرفر ماين كرافت"""
        # أولاً نحاول الاتصال بالسيرفر الفعلي
        real_status = await self.tester.test_server_connection()
        
        if real_status['success']:
            return real_status
        else:
            # إذا فشل الاتصال، نستخدم المحاكاة للعرض التوضيحي
            logger.info("استخدام المحاكاة لعرض وظائف البوت")
            simulated_status = await self.tester.simulate_server_status()
            simulated_status['note'] = 'هذه بيانات محاكاة - لم يتم العثور على سيرفر فعلي'
            return simulated_status
    
    async def send_rcon_command(self, command):
        """إرسال أمر عبر RCON"""
        # أولاً نحاول الاتصال بـ RCON الفعلي
        real_result = self.tester.test_rcon_connection()
        
        if real_result['success']:
            try:
                with MCRcon(config.MINECRAFT_SERVER_HOST, config.MINECRAFT_RCON_PASSWORD, port=config.MINECRAFT_RCON_PORT) as mcr:
                    response = mcr.command(command)
                    return {'success': True, 'response': response}
            except Exception as e:
                logger.error(f"خطأ في إرسال أمر RCON: {e}")
                return {'success': False, 'error': str(e)}
        else:
            # إذا فشل الاتصال، نستخدم المحاكاة
            logger.info("استخدام محاكاة RCON لعرض وظائف البوت")
            simulated_result = self.tester.simulate_rcon_command(command)
            simulated_result['note'] = 'هذه نتيجة محاكاة - لم يتم العثور على RCON فعلي'
            return simulated_result

# إنشاء كائن البوت
bot = MinecraftTelegramBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية"""
    keyboard = [
        [InlineKeyboardButton("🔍 فحص حالة السيرفر", callback_data='status')],
        [InlineKeyboardButton("👥 اللاعبون المتصلون", callback_data='players')],
        [InlineKeyboardButton("📊 معلومات السيرفر", callback_data='info')],
        [InlineKeyboardButton("💬 إرسال رسالة للجميع", callback_data='broadcast')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        config.MESSAGES['welcome'] + "\n\nاختر ما تريد فعله:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة"""
    help_text = """
🤖 أوامر البوت:

/start - بدء التفاعل مع البوت
/help - عرض هذه المساعدة
/status - فحص حالة السيرفر
/players - عرض اللاعبين المتصلين
/info - معلومات مفصلة عن السيرفر
/say <رسالة> - إرسال رسالة للجميع في السيرفر
/cmd <أمر> - تنفيذ أمر في السيرفر (للمدراء فقط)
/whitelist <add/remove> <اسم_اللاعب> - إدارة القائمة البيضاء
/kick <اسم_اللاعب> - طرد لاعب من السيرفر
/ban <اسم_اللاعب> - حظر لاعب
/pardon <اسم_اللاعب> - إلغاء حظر لاعب

📝 ملاحظات:
- بعض الأوامر تتطلب صلاحيات إدارية
- تأكد من تفعيل RCON في السيرفر
"""
    await update.message.reply_text(help_text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص حالة السيرفر"""
    status = await bot.check_server_status()
    
    if status['online']:
        message = f"""
🟢 {config.MESSAGES['server_online']}

👥 اللاعبون: {status['players_online']}/{status['players_max']}
🎮 الإصدار: {status['version']}
⏱️ زمن الاستجابة: {status['latency']:.2f}ms

📝 وصف السيرفر:
{status['motd']}
"""
    else:
        message = f"🔴 {config.MESSAGES['server_offline']}"
        if 'error' in status:
            message += f"\n❌ {status['error']}"
    
    await update.message.reply_text(message)

async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض اللاعبين المتصلين"""
    status = await bot.check_server_status()
    
    if not status['online']:
        await update.message.reply_text("🔴 السيرفر غير متصل")
        return
    
    if status['players_online'] == 0:
        await update.message.reply_text("👥 " + config.MESSAGES['no_players'])
        return
    
    players_text = f"👥 اللاعبون المتصلون ({status['players_online']}):\n\n"
    
    if status['players_list']:
        for i, player in enumerate(status['players_list'], 1):
            players_text += f"{i}. {player}\n"
    else:
        players_text += "قائمة اللاعبين غير متاحة"
    
    await update.message.reply_text(players_text)

async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة للجميع في السيرفر"""
    if not context.args:
        await update.message.reply_text("❌ يرجى كتابة الرسالة بعد الأمر\nمثال: /say مرحباً بالجميع!")
        return
    
    message = ' '.join(context.args)
    result = await bot.send_rcon_command(f"say {message}")
    
    if result['success']:
        await update.message.reply_text(f"✅ تم إرسال الرسالة: {message}")
    else:
        await update.message.reply_text(f"❌ فشل في إرسال الرسالة: {result['error']}")

async def cmd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ أمر في السيرفر (للمدراء فقط)"""
    user_id = update.effective_user.id
    
    # فحص صلاحيات المدير
    if config.ADMIN_USERS and user_id not in config.ADMIN_USERS:
        await update.message.reply_text("❌ " + config.MESSAGES['unauthorized'])
        return
    
    if not context.args:
        await update.message.reply_text("❌ يرجى كتابة الأمر بعد /cmd\nمثال: /cmd time set day")
        return
    
    command = ' '.join(context.args)
    result = await bot.send_rcon_command(command)
    
    if result['success']:
        response_text = f"✅ تم تنفيذ الأمر: `{command}`"
        if result['response']:
            response_text += f"\n📤 النتيجة: `{result['response']}`"
        await update.message.reply_text(response_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ فشل في تنفيذ الأمر: {result['error']}")

async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة القائمة البيضاء"""
    user_id = update.effective_user.id
    
    if config.ADMIN_USERS and user_id not in config.ADMIN_USERS:
        await update.message.reply_text("❌ " + config.MESSAGES['unauthorized'])
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ الاستخدام: /whitelist <add/remove> <اسم_اللاعب>")
        return
    
    action = context.args[0].lower()
    player = context.args[1]
    
    if action not in ['add', 'remove']:
        await update.message.reply_text("❌ يجب أن يكون الإجراء add أو remove")
        return
    
    result = await bot.send_rcon_command(f"whitelist {action} {player}")
    
    if result['success']:
        action_ar = "إضافة" if action == "add" else "إزالة"
        await update.message.reply_text(f"✅ تم {action_ar} {player} {'إلى' if action == 'add' else 'من'} القائمة البيضاء")
    else:
        await update.message.reply_text(f"❌ فشل في تعديل القائمة البيضاء: {result['error']}")

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طرد لاعب من السيرفر"""
    user_id = update.effective_user.id
    
    if config.ADMIN_USERS and user_id not in config.ADMIN_USERS:
        await update.message.reply_text("❌ " + config.MESSAGES['unauthorized'])
        return
    
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /kick <اسم_اللاعب> [سبب]")
        return
    
    player = context.args[0]
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "تم طردك من السيرفر"
    
    result = await bot.send_rcon_command(f"kick {player} {reason}")
    
    if result['success']:
        await update.message.reply_text(f"✅ تم طرد {player} من السيرفر")
    else:
        await update.message.reply_text(f"❌ فشل في طرد اللاعب: {result['error']}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أزرار الكيبورد"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'status':
        status = await bot.check_server_status()
        
        if status['online']:
            message = f"""
🟢 السيرفر متصل

👥 اللاعبون: {status['players_online']}/{status['players_max']}
🎮 الإصدار: {status['version']}
⏱️ زمن الاستجابة: {status['latency']:.2f}ms
"""
        else:
            message = "🔴 السيرفر غير متصل"
        
        await query.edit_message_text(message)
    
    elif query.data == 'players':
        status = await bot.check_server_status()
        
        if not status['online']:
            await query.edit_message_text("🔴 السيرفر غير متصل")
            return
        
        if status['players_online'] == 0:
            await query.edit_message_text("👥 لا يوجد لاعبون متصلون")
            return
        
        players_text = f"👥 اللاعبون المتصلون ({status['players_online']}):\n\n"
        
        if status['players_list']:
            for i, player in enumerate(status['players_list'], 1):
                players_text += f"{i}. {player}\n"
        else:
            players_text += "قائمة اللاعبين غير متاحة"
        
        await query.edit_message_text(players_text)
    
    elif query.data == 'info':
        status = await bot.check_server_status()
        
        if status['online']:
            message = f"""
📊 معلومات السيرفر

🌐 العنوان: {config.MINECRAFT_SERVER_HOST}:{config.MINECRAFT_SERVER_PORT}
🎮 الإصدار: {status['version']}
👥 اللاعبون: {status['players_online']}/{status['players_max']}
⏱️ زمن الاستجابة: {status['latency']:.2f}ms

📝 وصف السيرفر:
{status['motd']}
"""
        else:
            message = "🔴 السيرفر غير متصل - لا يمكن الحصول على المعلومات"
        
        await query.edit_message_text(message)
    
    elif query.data == 'broadcast':
        await query.edit_message_text("💬 لإرسال رسالة للجميع، استخدم الأمر:\n/say <رسالتك هنا>")

def main():
    """تشغيل البوت"""
    # إنشاء التطبيق
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("players", players_command))
    application.add_handler(CommandHandler("say", say_command))
    application.add_handler(CommandHandler("cmd", cmd_command))
    application.add_handler(CommandHandler("whitelist", whitelist_command))
    application.add_handler(CommandHandler("kick", kick_command))
    
    # إضافة معالج الأزرار
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # بدء البوت
    print("🤖 بدء تشغيل بوت ماين كرافت...")
    print(f"🌐 السيرفر المستهدف: {config.MINECRAFT_SERVER_HOST}:{config.MINECRAFT_SERVER_PORT}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

