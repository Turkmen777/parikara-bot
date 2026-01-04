import logging
import sys
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from config import *

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Хранение данных
deposits = []
next_id = 1000

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = [[KeyboardButton("💰 Пополнить счет")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    keyboard = [[KeyboardButton("❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========== СТАРТ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇹🇲 <b>Parikara Bot</b>\n\nПривет! Нажмите кнопку:",
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

# ========== ОБРАБОТКА СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    # Если это группа
    if update.effective_chat.id == GROUP_CHAT_ID:
        await handle_group_message(update, context)
        return
    
    # Если это клиент
    if text == "💰 Пополнить счет":
        await update.message.reply_text(
            "Введите ваш ID в системе Parikara:",
            reply_markup=get_cancel_keyboard()
        )
        context.user_data["step"] = "wait_id"
        
    elif text == "❌ Отмена":
        await update.message.reply_text("Отменено", reply_markup=get_main_keyboard())
        context.user_data.clear()
        
    elif "step" in context.user_data:
        if context.user_data["step"] == "wait_id":
            context.user_data["client_id"] = text
            context.user_data["step"] = "wait_amount"
            await update.message.reply_text(f"Введите сумму (мин. {MIN_AMOUNT} TMT):")
            
        elif context.user_data["step"] == "wait_amount":
            try:
                amount = float(text.replace(',', '.'))
                
                if amount < MIN_AMOUNT:
                    await update.message.reply_text(f"❌ Минимум {MIN_AMOUNT} TMT")
                    return
                
                global next_id, deposits
                
                # Создаем заявку
                deposit = {
                    "id": next_id,
                    "user_id": user.id,
                    "user_name": user.first_name,
                    "client_id": context.user_data["client_id"],
                    "amount": amount,
                    "time": datetime.now().strftime("%H:%M %d.%m.%Y"),
                    "status": "waiting"
                }
                
                deposits.append(deposit)
                
                # Клиенту
                await update.message.reply_text(
                    f"✅ <b>Заявка #{next_id} принята!</b>\n\nОжидайте реквизиты...",
                    parse_mode='HTML',
                    reply_markup=get_main_keyboard()
                )
                
                # В группу
                try:
                    group_msg = f"""
🆕 <b>НОВАЯ ЗАЯВКА #{next_id}</b>

👤 Клиент: {user.first_name}
📞 ID: {context.user_data['client_id']}
💰 Сумма: {amount} TMT
⏰ Время: {deposit['time']}

<b>Отправьте 8 цифр номера:</b>
                    """
                    
                    await context.bot.send_message(
                        chat_id=GROUP_CHAT_ID,
                        text=group_msg,
                        parse_mode='HTML'
                    )
                    logger.info(f"✅ Заявка #{next_id} отправлена в группу")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки в группу: {e}")
                
                next_id += 1
                context.user_data.clear()
                
            except ValueError:
                await update.message.reply_text("❌ Введите число!")

# ========== ОБРАБОТКА ГРУППЫ ==========
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ пишет номер в группе"""
    
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    logger.info(f"Сообщение в группе: {text}")
    
    # Проверяем, 8 ли это цифр
    if text.isdigit() and len(text) == 8:
        global deposits
        
        # Ищем последнюю заявку
        last_deposit = None
        for deposit in deposits:
            if deposit["status"] == "waiting" and "phone" not in deposit:
                last_deposit = deposit
                break
        
        if not last_deposit:
            await update.message.reply_text("❌ Нет заявок")
            return
        
        # Форматируем номер
        phone = f"+993 {text[:2]} {text[2:5]} {text[5:]}"
        
        # Сохраняем
        for i, deposit in enumerate(deposits):
            if deposit["id"] == last_deposit["id"]:
                deposits[i]["phone"] = phone
                break
        
        # Отправляем клиенту
        try:
            await context.bot.send_message(
                chat_id=last_deposit["user_id"],
                text=f"💳 <b>РЕКВИЗИТЫ</b>\n\nНомер: {phone}\nСумма: {last_deposit['amount']} TMT\n\nОтправьте скриншот!",
                parse_mode='HTML'
            )
            
            # В группе
            await update.message.reply_text(
                f"✅ Реквизиты отправлены клиенту #{last_deposit['id']}\nНомер: {phone}"
            )
            
            # Кнопка для подтверждения
            keyboard = [[InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{last_deposit['id']}")]]
            
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"⏳ Ожидаем скриншот #{last_deposit['id']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            logger.info(f"✅ Номер отправлен клиенту {last_deposit['user_id']}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            logger.error(f"Ошибка: {e}")

# ========== СКРИНШОТЫ ==========
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Ищем заявку
    user_deposit = None
    for deposit in deposits:
        if deposit["user_id"] == user_id and deposit.get("phone") and deposit["status"] == "waiting":
            user_deposit = deposit
            break
    
    if not user_deposit:
        await update.message.reply_text("❌ Нет активной заявки")
        return
    
    await update.message.reply_text("✅ Скриншот получен")
    
    # В группу
    try:
        photo = update.message.photo[-1]
        await context.bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=photo.file_id,
            caption=f"📸 Скриншот #{user_deposit['id']}"
        )
        
        keyboard = [[InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{user_deposit['id']}")]]
        
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"Скриншот от клиента #{user_deposit['id']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")

# ========== ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ==========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("confirm_"):
        deposit_id = int(query.data.split("_")[1])
        
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Только админ")
            return
        
        # Ищем заявку
        for i, deposit in enumerate(deposits):
            if deposit["id"] == deposit_id:
                deposits[i]["status"] = "completed"
                
                # Обновляем сообщение
                await query.edit_message_text(f"✅ Платеж #{deposit_id} подтвержден")
                
                # Клиенту
                try:
                    await context.bot.send_message(
                        chat_id=deposit["user_id"],
                        text=f"🎉 Счет пополнен на {deposit['amount']} TMT"
                    )
                except:
                    pass
                break

# ========== ЗАПУСК ==========
def main():
    print("=" * 60)
    print("🤖 БОТ PARIKARA ЗАПУЩЕН!")
    print("=" * 60)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.run_polling()

if __name__ == "__main__":
    main()