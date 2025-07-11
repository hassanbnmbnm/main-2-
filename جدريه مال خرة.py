import logging
import datetime
import asyncio
import threading
import re
import os

from queue import Queue
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup
from telethon import TelegramClient, functions
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# باقي الكود كما هو...

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="bot.log",
)

BOT_TOKEN = os.getenv("BOT_TOKEN") or "7789925503:AAFG6X4FA0pJZYl--89DpMbvoovm_ZUj8SQ"
API_ID = int(os.getenv("API_ID") or 21862970)
API_HASH = os.getenv("API_HASH") or "c136d4da6145f58bc8dcce0ec73ce358"

API_HELP_LINK = "https://my.telegram.org/apps"
OWNER_ID = 7391602624

def get_main_keyboard(user_id):
    buttons = [
        ["✅ تشغيل السورس", "❌ إيقاف السورس"],
        ["➕ إضافة حساب ثاني", "🗑️ حذف الجلسة"],
        ["🔢 اختيار شكل الأرقام"]
    ]
    if user_id == OWNER_ID:
        buttons[2].insert(0, "🕒 تغيير سرعة التحديث")
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

STATE_WAIT_API_ID = "WAIT_API_ID"
STATE_WAIT_API_HASH = "WAIT_API_HASH"
STATE_WAIT_PHONE = "WAIT_PHONE"
STATE_WAIT_CODE = "WAIT_CODE"
STATE_WAIT_PASSWORD = "WAIT_PASSWORD"
STATE_IDLE = "IDLE"
from pyrogram import Client as PyroClient
app = PyroClient("bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

telethon_loop = asyncio.new_event_loop()
def telethon_loop_thread():
    asyncio.set_event_loop(telethon_loop)
    telethon_loop.run_forever()
threading.Thread(target=telethon_loop_thread, daemon=True).start()

user_states = {}
user_temp_data = {}
user_sessions = {}
running_tasks = {}

def get_time_emoji():
    hour = datetime.datetime.now().hour
    if 5 <= hour < 11:
        return "🌅"
    elif 11 <= hour < 17:
        return "🌤"
    elif 17 <= hour < 20:
        return "🌇"
    else:
        return "🌙"

def style_numbers(text, style="normal"):
    numbers_map = {
        "arabic": str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"),
        "fancy": str.maketrans("0123456789", "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡"),
        "fancy2": str.maketrans("0123456789", "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")
    }
    return text.translate(numbers_map.get(style, {}))
async def update_name(session_name, api_id, api_hash, number_style, update_speed):
    print(f"✅ بدء تحديث الاسم للجلسة: sessions/{session_name}.session")
    with open(f"sessions/{session_name}.session", "r") as f:
        string_sess = f.read().strip()

    async with TelegramClient(StringSession(string_sess), api_id, api_hash, loop=telethon_loop) as user:
        await asyncio.sleep(1)
        while True:
            now = datetime.datetime.now()
            time_str = now.strftime("%I:%M %p")
            time_str = style_numbers(time_str, number_style)
            emoji = get_time_emoji()
            new_name = f"{time_str} {emoji}"
            try:
                print(f"🔁 سيتم تحديث الاسم إلى: {new_name}")
                await user(functions.account.UpdateProfileRequest(first_name=new_name))
                logging.info(f"✅ الاسم تم تحديثه: {new_name}")
                print(f"✅ الاسم تم تحديثه: {new_name}")
            except Exception as e:
                logging.error(f"⚠️ خطأ أثناء التحديث: {e}")
                print(f"⚠️ خطأ أثناء التحديث: {e}")
            seconds_to_next = update_speed - now.second % update_speed
            await asyncio.sleep(seconds_to_next)

async def telethon_send_code(user_id, phone, api_id, api_hash):
    client = TelegramClient(StringSession(), api_id, api_hash, loop=telethon_loop)
    await client.connect()
    sent = await client.send_code_request(phone)
    user_temp_data[user_id] = {
        "client": client,
        "phone": phone,
        "phone_code_hash": sent.phone_code_hash,
        "stage": "awaiting_code",
        "api_id": api_id,
        "api_hash": api_hash,
        "sessions": user_sessions.get(user_id, {}).get("sessions", [])
    }
    return """✅ تم إرسال كود التحقق.
✉️ أرسل الكود الذي وصلك مفصولًا
مثل: ﴿ 1 2 3 4 5 ﴾
أو عادياً 
﴿إذا واجهت مشاكل أرسله مفصولاً﴾"""

async def telethon_sign_in(user_id, code):
    data = user_temp_data.get(user_id)
    if not data:
        return "❌ لم أجد جلسة تسجيل دخول لك، أرسل رقم هاتفك أولاً."

    client = data["client"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        session_name = f"user_session_{user_id}_{phone[-4:]}"
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "api_id": api_id,
                "api_hash": api_hash,
                "sessions": []
            }
        if session_name not in user_sessions[user_id]["sessions"]:
            user_sessions[user_id]["sessions"].append(session_name)

        string_sess = StringSession.save(client.session)
        os.makedirs("sessions", exist_ok=True)
        with open(f"sessions/{session_name}.session", "w") as f:
            f.write(string_sess)

        await client.disconnect()
        user_temp_data.pop(user_id)
        user_states[user_id] = STATE_IDLE
        return "✅ تم تسجيل الدخول بنجاح!"
    except SessionPasswordNeededError:
        data["stage"] = "awaiting_password"
        return "🔐 الحساب مفعّل عليه التحقق بخطوتين. ✉️ أرسل كلمة المرور الآن."
    except Exception as e:
        error_msg = str(e)
        if "confirmation code has expired" in error_msg.lower() or "code is invalid" in error_msg.lower():
            user_states[user_id] = STATE_WAIT_PHONE
            user_temp_data.pop(user_id, None)
            return "❌ انتهت صلاحية كود التحقق أو غير صالح. 🔁 أرسل رقم الهاتف من جديد."
        return "❌ فشل تسجيل الدخول. تأكد من البيانات وحاول مرة أخرى."
async def telethon_sign_in_password(user_id, password):
    data = user_temp_data.get(user_id)
    if not data:
        return "❌ لا توجد جلسة حالية."
    client = data["client"]
    try:
        await client.sign_in(password=password)
        session_name = f"user_session_{user_id}_{data['phone'][-4:]}"
        string_sess = client.session.save()
        os.makedirs("sessions", exist_ok=True)
        with open(f"sessions/{session_name}.session", "w") as f:
            f.write(string_sess)
        await client.disconnect()
        user_temp_data.pop(user_id)
        user_states[user_id] = STATE_IDLE
        return "✅ تم تسجيل الدخول بعد التحقق من كلمة المرور!"
    except Exception:
        return "❌ فشل التحقق من كلمة المرور. حاول مرة أخرى."

async def start_update_task(user_id, session_name, message):
    api_id = user_sessions[user_id]["api_id"]
    api_hash = user_sessions[user_id]["api_hash"]
    number_style = user_sessions[user_id].get("number_style", "normal")
    update_speed = user_sessions[user_id].get("update_speed", 60)

    task_key = (user_id, session_name)
    if task_key in running_tasks:
        await message.reply("⚠️ السورس يعمل بالفعل لهذه الجلسة.")
        return

    from concurrent.futures import CancelledError

    future = asyncio.run_coroutine_threadsafe(
        update_name(session_name, api_id, api_hash, number_style, update_speed),
        telethon_loop
    )
    running_tasks[task_key] = future
    await message.reply(f"✅ تم تشغيل السورس على الجلسة {session_name}.")

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.chat.id
    if user_id not in user_sessions or not user_sessions[user_id].get("sessions"):
        user_states[user_id] = STATE_WAIT_API_ID
        await message.reply("🔑 أهلاً بك!\n__\n❄️تنويه اذا ناوي تستخدم البوت❄️\n__\n"
                            "الاوامر كالتالي :\n✅ تشغيل السورس\n___\n🔢 اختيار شكل الأرقام\n___\n❌ إيقاف السورس\n___\n"
                            "➕ إضافة حساب ثاني\n___\n🗑️ حذف الجلسة\n__\n"
                            "ترسل الامر كما مكتوب مع الرموز او الايموجي\n__\n"
                            "الان أرسل api_id الخاص بك:\n"
                            "إذا لم تكن تعرفه: استخرجة من الرابط https://my.telegram.org/apps")
    else:
        custom_keyboard = ReplyKeyboardMarkup(
            [
                ["✅ تشغيل السورس", "❌ إيقاف السورس"],
                ["➕ إضافة حساب ثاني", "🗑️ حذف الجلسة"],
                ["🔢 اختيار شكل الأرقام"]
            ],
            resize_keyboard=True
        )
        await message.reply("👋 أهلاً بعودتك!", reply_markup=custom_keyboard)
        user_states[user_id] = STATE_IDLE
@app.on_message(filters.private & filters.text)
async def handle_states(client, message):
    user_id = message.chat.id
    text = message.text.strip()
    state = user_states.get(user_id, STATE_IDLE)
    temp_data = user_temp_data.setdefault(user_id, {})

    if state == STATE_IDLE:
        if text == "✅ تشغيل السورس":
            session_list = user_sessions.get(user_id, {}).get("sessions", [])
            if not session_list:
                await message.reply("❌ لا يوجد حساب لتشغيل السورس عليه.")
                return
            if len(session_list) == 1:
                await start_update_task(user_id, session_list[0], message)
            else:
                buttons = [[sess] for sess in session_list]
                await message.reply("💡 اختر الجلسة التي تريد تشغيل السورس عليها:", 
                    reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
                user_states[user_id] = "WAIT_SESSION_SELECTION"
            return

        elif text == "❌ إيقاف السورس":
            to_remove = [k for k in running_tasks if k[0] == user_id]
            if not to_remove:
                await message.reply("⚠️ السورس غير مفعّل حالياً.")
            for key in to_remove:
                future = running_tasks.pop(key)
                future.cancel()
            await message.reply("🛑 تم إيقاف جميع الجلسات.")

        elif text == "🔢 اختيار شكل الأرقام":
            await message.reply("🔢 اختر نوع الأرقام: normal | arabic | fancy | fancy2")
            user_states[user_id] = "WAIT_NUMBER_STYLE"

        elif text == "🗑️ حذف الجلسة":
            user_sessions.pop(user_id, None)
            for key in list(running_tasks):
                if key[0] == user_id:
                    running_tasks[key].cancel()
                    del running_tasks[key]
            await message.reply("🗑️ تم حذف كل الجلسات وإيقاف التحديث.")

        elif text == "➕ إضافة حساب ثاني":
            user_states[user_id] = STATE_WAIT_API_ID
            await message.reply("🔑 أرسل الـ API ID للحساب الجديد:")

        else:
            await message.reply("📩 لم أفهم الأمر. استخدم الأزرار.")

    elif state == "WAIT_SESSION_SELECTION":
        if text in user_sessions[user_id]["sessions"]:
            await start_update_task(user_id, text, message)
            user_states[user_id] = STATE_IDLE
        else:
            await message.reply("❌ الجلسة غير موجودة. حاول مجددًا.")

    elif state == STATE_WAIT_API_ID:
        if text.isdigit():
            temp_data["api_id"] = int(text)
            user_states[user_id] = STATE_WAIT_API_HASH
            await message.reply("🔑 أرسل الآن `api_hash` الخاص بك:")
        else:
            await message.reply("❌ api_id يجب أن يكون رقم.")

    elif state == STATE_WAIT_API_HASH:
        if text:
            temp_data["api_hash"] = text
            user_sessions[user_id] = {
                "api_id": temp_data["api_id"],
                "api_hash": temp_data["api_hash"],
                "sessions": [],
                "update_speed": 60,
                "number_style": "normal"
            }
            user_states[user_id] = STATE_WAIT_PHONE
            await message.reply("📱 أرسل رقم هاتفك مع رمز الدولة (مثال: +9665xxxxxxx):")

    elif state == STATE_WAIT_PHONE:
        if text.startswith("+") and text[1:].isdigit():
            api_id = user_sessions[user_id]["api_id"]
            api_hash = user_sessions[user_id]["api_hash"]
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    telethon_send_code(user_id, text, api_id, api_hash), telethon_loop
                )
                result = fut.result(timeout=15)
                user_states[user_id] = STATE_WAIT_CODE
                await message.reply(result)
            except Exception:
                await message.reply("❌ فشل في إرسال الكود.")
        else:
            await message.reply("❌ رقم الهاتف غير صحيح. مثال: +9665xxxxxxx")

    elif state == STATE_WAIT_CODE:
        code = ''.join(re.findall(r'\d', text))
        if len(code) < 4:
            await message.reply("❗ الرجاء إرسال كود التحقق بشكل صحيح.")
            return
        fut = asyncio.run_coroutine_threadsafe(
            telethon_sign_in(user_id, code), telethon_loop
        )
        result = fut.result()
        await message.reply(result)

    elif state == STATE_WAIT_PASSWORD:
        fut = asyncio.run_coroutine_threadsafe(
            telethon_sign_in_password(user_id, text), telethon_loop
        )
        result = fut.result()
        await message.reply(result)

    elif state == "WAIT_NUMBER_STYLE":
        if text in ["normal", "arabic", "fancy", "fancy2"]:
            user_sessions[user_id]["number_style"] = text
            user_states[user_id] = STATE_IDLE
            await message.reply(f"✅ تم اختيار نوع الأرقام: {text}")
        else:
            await message.reply("❌ نوع غير معروف. جرب: normal, arabic, fancy, fancy2")

if __name__ == "__main__":
    if not os.path.exists("sessions"):
        os.makedirs("sessions")
    app.run()