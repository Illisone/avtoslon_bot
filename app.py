import logging
from telegram import (
    Update, 
    Message,         
    KeyboardButton, 
    ReplyKeyboardMarkup, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    InputMediaPhoto, 
    InputMediaVideo,
    WebAppInfo
)
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os 
import time 
import json 
import asyncio 
import re 
import io 
from typing import List 

# Импорт констант из texts.py
from texts import (
    TEXT_COMPANY_CAPTION_1, TEXT_COMPANY_PART_2_FULL, 
    PARTNERSHIP_DETAILS_FULL, 
    TEXT_DRIVE_CARD, TEXT_CONTACTS,
    TEXT_CLIENTS_CAPTION,
    MINI_APP_URL, CATALOG_URL, MANAGER_LINK, GENERAL_CHAT_URL, 
    DRIVE_CARD_LINK, GIS_LINK, TELEGRAM_LINK,
    FAQ_APP_URL, CONTACTS_APP_URL
)


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


TOKEN = '8519347269:AAG0LRbbnj9X_4xEwzRTq9TAG_NKJ60lAXM'

# --- ИСПРАВЛЕНИЕ ПУТЕЙ: ИСПОЛЬЗУЕМ АБСОЛЮТНЫЙ ПУТЬ ДЛЯ НАДЕЖНОСТИ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_CLIENTS_PATH = os.path.join(BASE_DIR, "images", "clients_photo.jpg")
PHOTO_PARTNERSHIP_PATH = os.path.join(BASE_DIR, "images", "partnership_photo.jpg")
PHOTO_COMPANY_PATH = os.path.join(BASE_DIR, "images", "company_photo.jpg")
# ---------------------------------------------------------------------

# ==========================================================
# КОНСТАНТЫ
STAFF_USER_ID = 5902674657  # <--- ВАШ ID ЗДЕСЬ
SERVICE_CHAT_ID = STAFF_USER_ID # Используем ID сотрудника для получения постоянного file_id
CARS_DATA_PATH = "cars_data.json" 
TAPLINK_URL = "https://taplink.cc/avtoslon" 
MEDIA_GROUP_TIMEOUT = 1.0 

# --- ФУТЕР (УПРОЩЕНИЕ: убран вопрос "Хотите приобрести?" для стабильности парсинга) ---
LINKABLE_CONTACT_PHRASE = f"[СВЯЗАТЬСЯ С НАМИ ЛЮБЫМ УДОБНЫМ СПОСОБОМ]({TAPLINK_URL})"

FINAL_FOOTER = (
    "\n\n⬇️⬇️⬇️\n"
    f"{LINKABLE_CONTACT_PHRASE}"
)

FOOTER_CLEANING_PATTERN = r'\s*Хотите приобрести автомобиль\?\s*⬇️⬇️⬇️\s*СВЯЗАТЬСЯ С НАМИ ЛЮБЫМ УДОБНЫМ СПОСОБОМ(?:\s*\([^)]*\))?\s*$'

BTN_APP = "Бесплатный подбор авто" 
BTN_CATALOG = "Каталог авто" 
BTN_COMPANY = "О компании"
BTN_PARTNER = "Заработайте с нами"
BTN_AVAILABLE = "В наличии"
BTN_DRIVE = "Карточка дром"
BTN_CLIENTS = "Клиенты"
BTN_CHAT = "Общий чат"
BTN_CONTACTS = "Контакты"
BTN_FAQ = "Популярные вопросы"


def load_cars_data():
    """Загружает список авто из JSON-файла."""
    try:
        with open(CARS_DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_cars_data(data):
    """Сохраняет список авто в JSON-файл."""
    with open(CARS_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
# ----------------------------------------


# --- Функции для клавиатур ---
def build_client_inline_keyboard():
    keyboard = [[InlineKeyboardButton("⭐ 2Gis", url=GIS_LINK), InlineKeyboardButton("💬 Telegram", url=TELEGRAM_LINK)]]
    return InlineKeyboardMarkup(keyboard)

def build_partnership_inline_keyboard():
    keyboard = [[InlineKeyboardButton("✍️ Написать менеджеру", url=MANAGER_LINK)]]
    return InlineKeyboardMarkup(keyboard)


def build_spacer_inline_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("\u200b", callback_data="ignore")]])

# ⚠️ ИСПРАВЛЕНИЕ: Кнопка BTN_APP теперь содержит web_app
def build_reply_keyboard():
    app_button = KeyboardButton(BTN_APP, web_app=WebAppInfo(url=MINI_APP_URL))
    faq_app_button = KeyboardButton(BTN_FAQ, web_app=WebAppInfo(url=FAQ_APP_URL))
    contacts_button = KeyboardButton(BTN_CONTACTS, web_app=WebAppInfo(url=CONTACTS_APP_URL))
    
    keyboard = [
        [app_button],
        [faq_app_button],
        [contacts_button], # <-- ВОТ ЗДЕСЬ БЫЛА ПРОПУЩЕНА ЗАПЯТАЯ
        [KeyboardButton(BTN_CATALOG)],
        [KeyboardButton(BTN_COMPANY), KeyboardButton(BTN_PARTNER)],
        [KeyboardButton(BTN_AVAILABLE), KeyboardButton(BTN_DRIVE)],
        [KeyboardButton(BTN_CLIENTS), KeyboardButton(BTN_CHAT)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ==========================================================
# ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ПОСТОЯННОГО FILE_ID 
# ==========================================================
async def _get_permanent_file_id(file_id: str, media_type: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Получает медиа и переотправляет его в сервисный чат, чтобы получить постоянный file_id."""
    
    if SERVICE_CHAT_ID == 0:
        return file_id
        
    try:
        file = await context.bot.get_file(file_id)
        
        # Загружаем содержимое файла в поток io.BytesIO
        byte_stream = io.BytesIO()
        await file.download(out=byte_stream)
        byte_stream.seek(0)
        
        temp_msg = None
        
        # Переотправляем в SERVICE_CHAT_ID для получения постоянного ID
        if media_type == "photo":
            temp_msg = await context.bot.send_photo(
                chat_id=SERVICE_CHAT_ID, 
                photo=byte_stream, 
                caption="\u200b", 
                disable_notification=True
            )
            # Новый ID - это ID самого большого размера фото
            return temp_msg.photo[-1].file_id
            
        elif media_type == "video":
            temp_msg = await context.bot.send_video(
                chat_id=SERVICE_CHAT_ID, 
                video=byte_stream, 
                caption="\u200b",
                disable_notification=True
            )
            return temp_msg.video.file_id
            
    except Exception as e:
        logging.error(f"❌ Критическая ошибка при получении постоянного file_id ({media_type}, ID {file_id}): {e}. Используем оригинальный ID.")
        return file_id 
# ==========================================================


# ==========================================================
# ОСНОВНАЯ ЛОГИКА ДОБАВЛЕНИЯ АВТО
# ==========================================================
async def _add_car_logic(message_list: List[Message], update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    new_cars_text = ""
    media_list = []
    
    # 1. Сбор текста и всех медиа ID (и получение постоянного file_id)
    for message in message_list:
        if message.caption and not new_cars_text:
            new_cars_text = message.caption
        elif message.text and not new_cars_text:
            new_cars_text = message.text
            
        # Получение надежного file_id
        if message.photo:
            original_file_id = message.photo[-1].file_id
            permanent_file_id = await _get_permanent_file_id(original_file_id, "photo", context)
            media_list.append({"type": "photo", "file_id": permanent_file_id})
            
        elif message.video:
            original_file_id = message.video.file_id
            permanent_file_id = await _get_permanent_file_id(original_file_id, "video", context)
            media_list.append({"type": "video", "file_id": permanent_file_id})
            
    if not new_cars_text.strip() and not media_list:
        if update.message:
            await update.message.reply_text("❗ Пересланный пост не содержит текста или медиа. Сохранение отменено.")
        return

    # 2. МИНИМАЛЬНАЯ ОЧИСТКА для устранения дублирования футера
    final_car_text = new_cars_text.strip() if new_cars_text.strip() else "Нет описания."
    
    # Очищаем дублирующийся футер с конца текста
    cleaned_text = re.sub(FOOTER_CLEANING_PATTERN, '', final_car_text, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
    final_car_text = cleaned_text.strip()
    
    # 3. Сохранение данных
    try:
        cars_list = load_cars_data() 
        
        max_id = max((car.get('id', 0) for car in cars_list), default=0)
        new_id = max_id + 1
        
        new_car = {
            "id": new_id,
            "text": final_car_text, 
            "media": media_list,
            "added_at": time.strftime('%d.%m.%Y %H:%M')
        }
        
        cars_list.append(new_car)
        save_cars_data(cars_list)

        media_count = len(media_list)
        await update.message.reply_text(
            f"✅ Автомобиль №**{new_id}** успешно **добавлен**! ({media_count} фото/видео). Сейчас в наличии: **{len(cars_list)}**.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Ошибка в логике добавления авто: {e}")
        if update.message:
            await update.message.reply_text(f"❌ Произошла ошибка при автоматическом добавлении автомобиля: {e}")


# ==========================================================
# АСИНХРОННАЯ ФУНКЦИЯ ДЛЯ СБОРА АЛЬБОМА ПО ТАЙМАУТУ
# ==========================================================
async def _process_media_group_after_delay(group_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.sleep(MEDIA_GROUP_TIMEOUT)
    
    media_groups = context.application.media_groups_buffer
    message_list = media_groups.pop(group_id, None)
    
    if message_list:
        first_message = message_list[0]
        try:
            temp_update = Update(update_id=0, message=first_message) 
            await _add_car_logic(message_list, temp_update, context)
        except Exception as e:
             logging.error(f"Ошибка при обработке альбома {group_id}: {e}")
             if first_message.chat_id:
                  await context.bot.send_message(first_message.chat_id, f"❌ Произошла критическая ошибка при обработке альбома: {e}")


# ==========================================================
# ОБРАБОТЧИК ДЛЯ АВТОМАТИЧЕСКОГО ДОБАВЛЕНИЯ
# ==========================================================
async def staff_forward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    
    if update.effective_user.id != STAFF_USER_ID:
        return
    
    if message.media_group_id:
        group_id = message.media_group_id
        
        media_groups = context.application.media_groups_buffer

        media_groups.setdefault(group_id, []).append(message)

        if len(media_groups[group_id]) == 1:
            context.application.create_task(
                _process_media_group_after_delay(group_id, context)
            )
        return

    has_content = bool(message.text or message.caption or message.photo or message.video)
    
    if has_content:
        await _add_car_logic([message], update, context)


# ==========================================================
# ОБРАБОТЧИК ДЛЯ УДАЛЕНИЯ АВТО ИЗ СПИСКА (/del)
# ==========================================================
async def del_car_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    if update.effective_user.id != STAFF_USER_ID:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    reply_message = update.message.reply_to_message
    if not reply_message:
        await update.message.reply_text("❗ Для удаления ответьте этой командой на пост с автомобилем, который нужно удалить.")
        return

    reply_text = reply_message.caption if reply_message.caption else reply_message.text
    
    if not reply_text:
        await update.message.reply_text("❌ В сообщении, на которое вы ответили, нет текста. Невозможно найти авто для удаления.")
        return

    cars_list = load_cars_data()
    
    try:
        # Ищем ID в новом, более гибком формате ID:**ID**
        match = re.search(r"ID:\s*[\*:]*(\d+)", reply_text) 
        car_id_to_delete = int(match.group(1)) if match else None
    except Exception:
        car_id_to_delete = None

    if car_id_to_delete is not None:
        original_count = len(cars_list)
        new_cars_list = [car for car in cars_list if car.get('id') != car_id_to_delete]
        
        if len(new_cars_list) < original_count:
            save_cars_data(new_cars_list)
            await update.message.reply_text(
                f"✅ Автомобиль №**{car_id_to_delete}** успешно **удален** из наличия. Осталось: **{len(new_cars_list)}**.",
                parse_mode='Markdown'
            )
            return
    
    await update.message.reply_text("❌ Не удалось найти ID автомобиля в тексте поста, на который вы ответили.")


# ==========================================================
# НОВЫЙ ОБРАБОТЧИК ДЛЯ ДАННЫХ MINI APP
# ==========================================================
async def web_app_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает данные, пришедшие из Telegram Mini App (filters.StatusUpdate.WEB_APP_DATA)."""
    
    message = update.effective_message
    if not message.web_app_data or not message.web_app_data.data:
        return

    # Получаем данные в виде строки (JSON)
    data_json = message.web_app_data.data
    
    try:
        data = json.loads(data_json)
        
        # Форматируем сообщение для отправки вам (STAFF)
        report_text = f"🚨 **НОВАЯ ЗАЯВКА НА ПОДБОР АВТО ИЗ MINI APP** 🚨\n\n"
        
        # Получаем данные о пользователе из сообщения WebApp 
        user = message.from_user
        user_id = user.id
        user_name = user.full_name
        user_username = user.username
        
        report_text += f"👤 **От:** [{user_name}](tg://user?id={user_id})\n" # Ссылка на пользователя
        report_text += f"💬 **Username:** @{user_username or 'нет'}\n\n"
        
        # Добавляем данные из формы
        for key, value in data.items():
            # Простая очистка ключа для вывода
            clean_key = key.replace('_', ' ').capitalize() 
            report_text += f"▪️ **{clean_key}:** {value}\n"
            
        # Отправляем вам (STAFF)
        await context.bot.send_message(
            chat_id=STAFF_USER_ID,
            text=report_text,
            parse_mode='Markdown'
        )
        
        # Отправляем подтверждение пользователю
        await message.reply_text("✅ Ваша заявка принята! Менеджер свяжется с вами в ближайшее время.")
        
    except json.JSONDecodeError:
        logging.error(f"Ошибка декодирования JSON из Web App: {data_json}")
        await message.reply_text("❌ Извините, произошла ошибка при отправке данных. Пожалуйста, попробуйте еще раз.")
    except Exception as e:
        logging.error(f"Критическая ошибка в web_app_handler: {e}")
        await message.reply_text("❌ Извините, произошла внутренняя ошибка при обработке данных.")
        
# ==========================================================


# ==========================================================
# ОБРАБОТЧИКИ КОМАНД И КНОПОК
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_message = "👋 Добро пожаловать! Выберите нужный раздел в меню ниже:"
    await update.message.reply_text(
        welcome_message,
        reply_markup=build_reply_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    response_text = None

    # --- ПРЯМЫЕ ССЫЛКИ ---
    # Обработка BTN_APP (Бесплатный подбор авто) удалена, так как она открывается автоматически 
    # через WebAppInfo в build_reply_keyboard().

    if user_text == BTN_CATALOG:
        await update.message.reply_text(
            "🏎️ Нажмите для перехода в каталог:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("КАТАЛОГ АВТО", url=CATALOG_URL)]])
        )
        return

    elif user_text == BTN_DRIVE:
        await update.message.reply_text(
            "✅ Проверить нашу репутацию и отзывы:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Карточка дром", url=DRIVE_CARD_LINK)]])
        )
        return

    elif user_text == BTN_CHAT:
        await update.message.reply_text(
            "💬 Присоединяйтесь к нашему чату:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Перейти в чат", url=GENERAL_CHAT_URL)]])
        )
        return

    # --- ДИНАМИЧЕСКИЙ ОТВЕТ: 5. В НАЛИЧИИ ---
    elif user_text == BTN_AVAILABLE:
        cars_list = load_cars_data()
        
        if not cars_list:
            await update.message.reply_text("❌ В наличии нет ни одного автомобиля.")
            return

        await update.message.reply_text(
            f"Актуальные предложения: {len(cars_list)}")

        
        for car in cars_list:
            content = car.get('text', 'Нет описания')
            media_list = car.get('media', [])
            car_id = car.get('id', 'N/A')
            
            # Новый, короткий формат ID и упрощенный футер
            display_content = f"ID:**{car_id}**\n\n" + content + FINAL_FOOTER
            
            text_sent = False

            # 4a. Отправка медиа-группы (альбома)
            if len(media_list) > 1:
                try:
                    media_group = []
                    
                    # Проверяем тип первого элемента перед созданием InputMedia
                    first_media = media_list[0]
                    if first_media['type'] == 'photo':
                        media_group.append(InputMediaPhoto(media=first_media['file_id'], caption=display_content, parse_mode='Markdown'))
                    elif first_media['type'] == 'video':
                        media_group.append(InputMediaVideo(media=first_media['file_id'], caption=display_content, parse_mode='Markdown'))
                    
                    # Проверяем и добавляем остальные элементы
                    for media_item in media_list[1:]:
                        if media_item['type'] == 'photo':
                            media_group.append(InputMediaPhoto(media=media_item['file_id']))
                        elif media_item['type'] == 'video':
                            media_group.append(InputMediaVideo(media=media_item['file_id']))
                    
                    await context.bot.send_media_group(
                        chat_id=update.effective_chat.id,
                        media=media_group
                    )
                    text_sent = True
                except Exception as e:
                    logging.error(f"Ошибка при отправке альбома ID {car_id}: {e}.")
            
            # 4b. Отправка одиночного фото/видео 
            elif len(media_list) == 1:
                media_item = media_list[0]
                try:
                    if media_item['type'] == 'photo':
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=media_item['file_id'],
                            caption=display_content, 
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                        text_sent = True
                    elif media_item['type'] == 'video':
                        await context.bot.send_video(
                            chat_id=update.effective_chat.id,
                            video=media_item['file_id'],
                            caption=display_content,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                        text_sent = True
                except Exception as e:
                    logging.error(f"Ошибка при отправке одиночного медиа для ID {car_id}: {e}.")
            
            # 4c. Отправка только текста (если медиа нет ИЛИ если медиа не отправилось)
            if not text_sent:
                 await context.bot.send_message( 
                    chat_id=update.effective_chat.id,
                    text=display_content, 
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )

        return

    # --- СТАНДАРТНЫЕ ТЕКСТОВЫЕ ОТВЕТЫ и КНОПКИ С ФОТОГРАФИЯМИ ---
    
    elif user_text == BTN_CONTACTS:
        response_text = TEXT_CONTACTS
    
    elif user_text == BTN_COMPANY:
        try:
            with open(PHOTO_COMPANY_PATH, 'rb') as photo_file:
                await update.message.reply_photo(photo=photo_file, caption=TEXT_COMPANY_CAPTION_1, parse_mode='Markdown')
            
            # Отправляем второй блок текста БЕЗ инлайн-клавиатуры
            await update.message.reply_text(
                TEXT_COMPANY_PART_2_FULL, 
                parse_mode='Markdown', 
                # УДАЛЕНО: reply_markup=build_company_inline_keyboard(),
                disable_web_page_preview=True
            )
            
        except FileNotFoundError:
            logging.error(f"Файл {PHOTO_COMPANY_PATH} не найден.")
            await update.message.reply_text("❗ Изображение для раздела 'О Компании' временно недоступно. Убедитесь, что файл company_photo.jpg находится в папке images.")
            
            await update.message.reply_text(
                TEXT_COMPANY_CAPTION_1, 
                parse_mode='Markdown', 
                reply_markup=build_spacer_inline_keyboard(), 
                disable_web_page_preview=True
            )
            await update.message.reply_text(
                TEXT_COMPANY_PART_2_FULL, 
                parse_mode='Markdown', 
                # УДАЛЕНО: reply_markup=build_company_inline_keyboard(),
                disable_web_page_preview=True
            )
        return

    elif user_text == BTN_PARTNER:
        try:
            with open(PHOTO_PARTNERSHIP_PATH, 'rb') as photo_file:
                await update.message.reply_photo(photo=photo_file, caption=PARTNERSHIP_DETAILS_FULL, parse_mode='Markdown', reply_markup=build_partnership_inline_keyboard())
        except FileNotFoundError:
            logging.error(f"Файл {PHOTO_PARTNERSHIP_PATH} не найден.")
            await update.message.reply_text("❗ Изображение для партнерской программы временно недоступно. Убедитесь, что файл partnership_photo.jpg находится в папке images.")
            await update.message.reply_text(PARTNERSHIP_DETAILS_FULL, parse_mode='Markdown', reply_markup=build_partnership_inline_keyboard(), disable_web_page_preview=True)
        return 

    elif user_text == BTN_CLIENTS:
        try:
            caption_text = f"""
💬 Мы искренне гордимся каждым отзывом — для нас это лучший показатель надежности и профессионализма. 
Ваше доверие вдохновляет нас становиться лучше с каждым днём.

📌 Убедитесь в нашей ответственности и компетентности — читайте независимые мнения и задавайте вопросы!
"""
            with open(PHOTO_CLIENTS_PATH, 'rb') as photo_file: 
                await update.message.reply_photo(photo=photo_file, caption=caption_text, parse_mode='Markdown', reply_markup=build_client_inline_keyboard())
        except FileNotFoundError:
            logging.error(f"Файл {PHOTO_CLIENTS_PATH} не найден.")
            await update.message.reply_text("❗ Изображение с отзывами временно недоступно. Убедитесь, что файл clients_photo.jpg находится в папке images.")
            await update.message.reply_text(caption_text, parse_mode='Markdown', reply_markup=build_client_inline_keyboard(), disable_web_page_preview=True)
        return 
    
    # --- ОБРАБОТКА ДРУГИХ СООБЩЕНИЙ ---
    else:
        if response_text is None:
            response_text = "❌ Неизвестная команда. Выберите кнопку из меню."

    if response_text:
        await update.message.reply_text(
            response_text,
            parse_mode='Markdown',
            disable_web_page_preview=True 
        )


def main() -> None:
    application = Application.builder().token(TOKEN).build()
    
    application.media_groups_buffer = {} 

    # 1. Обработчик для автоматического добавления авто при пересылке от STAFF_USER
    staff_forward_filter = (
        ~filters.COMMAND & filters.FORWARDED 
        & filters.User(STAFF_USER_ID)
    )
    application.add_handler(MessageHandler(staff_forward_filter, staff_forward_handler))
    
    # 2. Команда для удаления (теперь /del)
    application.add_handler(CommandHandler("del", del_car_handler)) 
    
    # 3. Обработчик для Mini App Data (НОВЫЙ)
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_handler)) 

    # 4. Основные обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    if not os.path.exists(CARS_DATA_PATH):
        try:
            with open(CARS_DATA_PATH, 'w', encoding='utf-8') as f:
                json.dump([], f)
        except Exception:
            logging.error("Не удалось создать файл cars_data.json")
    
    images_dir = os.path.join(BASE_DIR, "images")
    if not os.path.exists(images_dir):
         logging.warning(f"Папка 'images' не найдена. Создайте папку: {images_dir}")

    main()