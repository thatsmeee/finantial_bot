import telebot
from telebot import types
import sqlite3

API_TOKEN = '7248624438:AAEffysZJkUWtpg7gpglEJe889oMvs1QFdM'
OPERATOR_CHAT_IDS = ['1666259057', '1625312942']
bot = telebot.TeleBot(API_TOKEN)

courses_db_file = 'courses.db'
logs_db_file = 'logs.db'

# Инициализация баз данных
def init_dbs():
    with sqlite3.connect(courses_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT NOT NULL
            )
        """)
    with sqlite3.connect(logs_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                action TEXT,
                details TEXT
            )
        """)
    conn.commit()

# Запись лога в базу данных
def log_action(user_id, action, details):
    with sqlite3.connect(logs_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (user_id, action, details)
            VALUES (?, ?, ?)
        """, (user_id, action, details))
    conn.commit()

# Добавление курса в базу данных
def add_course_to_db(name, price, description):
    with sqlite3.connect(courses_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO courses (name, price, description)
            VALUES (?, ?, ?)
        """, (name, price, description))
    conn.commit()
    log_action(None, 'add_course', f"Name: {name}, Price: {price}, Description: {description}")

# Удаление курса из базы данных
def delete_course_from_db(course_id):
    with sqlite3.connect(courses_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM courses WHERE id = ?
        """, (course_id,))
    conn.commit()
    log_action(None, 'delete_course', f"Course ID: {course_id}")

# Получение всех курсов из базы данных
def get_courses_from_db():
    with sqlite3.connect(courses_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, price, description FROM courses
        """)
        courses = cursor.fetchall()
    return courses

# Получение курса по ID
def get_course_from_db(course_id):
    with sqlite3.connect(courses_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, price, description FROM courses WHERE id = ?
        """, (course_id,))
        course = cursor.fetchone()
    return course

# Создание главного меню
def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('Курсы', callback_data='courses'))
    markup.add(types.InlineKeyboardButton('Связаться с оператором', callback_data='contact_operator_main'))
    return markup

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите действие.", reply_markup=main_menu())
    log_action(message.from_user.id, 'start', 'Started interaction')

# Функция проверки, является ли пользователь администратором
def is_admin(user_id):
    return str(user_id) in OPERATOR_CHAT_IDS

# Старт процесса добавления курса
@bot.message_handler(commands=['add_course'])
def prompt_add_course(message):
    if is_admin(message.chat.id):
        bot.send_message(message.chat.id, "Введите название курса.")
        bot.register_next_step_handler(message, get_course_name)
        log_action(message.from_user.id, 'prompt_add_course', 'Prompted to enter course name')
    else:
        bot.send_message(message.chat.id, "У вас нет прав доступа к этой команде.")

def get_course_name(message):
    bot.chat_data = {'name': message.text}
    bot.send_message(message.chat.id, "Введите цену курса.")
    bot.register_next_step_handler(message, get_course_price)
    log_action(message.from_user.id, 'get_course_name', f"Name: {message.text}")

def get_course_price(message):
    try:
        bot.chat_data['price'] = int(message.text)
        bot.send_message(message.chat.id, "Введите описание курса.")
        bot.register_next_step_handler(message, get_course_description)
        log_action(message.from_user.id, 'get_course_price', f"Price: {message.text}")
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректную цену.")

def get_course_description(message):
    bot.chat_data['description'] = message.text
    name = bot.chat_data['name']
    price = bot.chat_data['price']
    description = bot.chat_data['description']
    add_course_to_db(name, price, description)
    bot.send_message(message.chat.id, f"Курс '{name}' добавлен.")
    log_action(message.from_user.id, 'add_course', f"Name: {name}, Price: {price}, Description: {description}")

# Обработчик команды /delete_course
@bot.message_handler(commands=['delete_course'])
def prompt_delete_course(message):
    if is_admin(message.chat.id):
        markup = types.InlineKeyboardMarkup()
        courses = get_courses_from_db()
        for course in courses:
            markup.add(types.InlineKeyboardButton(course[1], callback_data=f"delete_{course[0]}"))
        bot.send_message(message.chat.id, "Выберите курс для удаления:", reply_markup=markup)
        log_action(message.from_user.id, 'prompt_delete_course', 'Prompted to choose course to delete')
    else:
        bot.send_message(message.chat.id, "У вас нет прав доступа к этой команде.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_course(call):
    if is_admin(call.message.chat.id):
        course_id = int(call.data.split('_')[1])
        delete_course_from_db(course_id)
        bot.send_message(call.message.chat.id, "Курс удален.")
        log_action(call.from_user.id, 'delete_course', f"Course ID: {course_id}")
    else:
        bot.send_message(call.message.chat.id, "У вас нет прав доступа к этой команде.")

# Обработчик для просмотра курсов
@bot.callback_query_handler(func=lambda call: call.data == 'courses')
def list_courses(call):
    markup = types.InlineKeyboardMarkup()
    courses = get_courses_from_db()
    if courses:
        for course in courses:
            markup.add(types.InlineKeyboardButton(course[1], callback_data=f"view_{course[0]}"))
        bot.send_message(call.message.chat.id, "Выберите понравившийся Вам курс из списка и совершите оплату:", reply_markup=markup)
        log_action(call.from_user.id, 'list_courses', 'Listed available courses')
    else:
        bot.send_message(call.message.chat.id, "Курсы не найдены.")

# Обработчик для просмотра информации о курсе
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def view_course(call):
    course_id = int(call.data.split('_')[1])
    course = get_course_from_db(course_id)
    if course:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Связаться с оператором", callback_data=f"contact_operator_{course_id}"))
        web_info = types.WebAppInfo('https://thatsmeee.github.io/finantial/payment/crypto/index.html')
        web_info2 = types.WebAppInfo('https://thatsmeee.github.io/finantial/payment/mono/index.html')
        markup.add(types.InlineKeyboardButton("Оплата криптовалютой", web_app=web_info))
        markup.add(types.InlineKeyboardButton("Оплата картой ( 🇺🇦 )", web_app=web_info2))
        markup.add(types.InlineKeyboardButton("Я Оплатил", callback_data=f"payment_succeeded_{course_id}"))
        bot.send_message(call.message.chat.id,
                         f"{course[1]}\n\n{course[3]}\n\nЦена: ${course[2]}\n\nПожалуйста, свяжитесь с оператором для оплаты или перейдите по ссылке ниже.",
                         reply_markup=markup)
        log_action(call.from_user.id, 'view_course', f"Course ID: {course_id}")
    else:
        bot.send_message(call.message.chat.id, "Курс не найден.")

# Обработчик для связи с оператором
@bot.callback_query_handler(func=lambda call: call.data.startswith('contact_operator_'))
def contact_operator(call):
    course_id_str = call.data.split('_')[2]
    if course_id_str == 'main':
        bot.send_message(call.message.chat.id, "Пожалуйста, напишите ваше сообщение для оператора.")
        bot.register_next_step_handler(call.message, forward_to_operator_main)
        log_action(call.from_user.id, 'contact_operator_main', 'Requested to contact operator')
    else:
        try:
            course_id = int(course_id_str)
            course = get_course_from_db(course_id)
            if course:
                bot.send_message(call.message.chat.id, "Пожалуйста, напишите ваше сообщение для оператора.")
                bot.register_next_step_handler(call.message, forward_to_operator, course_id, call.message.message_id)
                log_action(call.from_user.id, 'contact_operator', f"Course ID: {course_id}")
            else:
                bot.send_message(call.message.chat.id, "Курс не найден.")
        except ValueError:
            bot.send_message(call.message.chat.id, "Ошибка в обработке запроса.")

# Обработчик для успешной оплаты
@bot.callback_query_handler(func=lambda call: call.data.startswith('payment_succeeded_'))
def payment_succeeded(call):
    user_username = call.from_user.username if call.from_user.username else "unknown"
    bot.send_message('-4275584152', f"Какой-то пользователь оплатил операцию. Проверьте. Его ник: {call.from_user.id} @{user_username}")
    log_action(call.from_user.id, 'payment_succeeded', f"Course ID: {call.data.split('_')[2]}")

def forward_to_operator(message, course_id, original_message_id):
    course = get_course_from_db(course_id)
    if course:
        forward_message = f"Пользователь @{message.from_user.username} ({message.from_user.id}) интересуется курсом '{course[1]}'.\n\nСообщение: {message.text}"
        for admin_id in OPERATOR_CHAT_IDS:
            bot.send_message(admin_id, forward_message)
        bot.send_message(message.chat.id, "Ваше сообщение отправлено операторам. Ожидайте ответа.")
        log_action(message.from_user.id, 'forward_to_operator', f"Message to operators about course ID: {course_id}")
    else:
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте снова.")

def forward_to_operator_main(message):
    forward_message = f"Пользователь @{message.from_user.username} ({message.from_user.id}) хочет связаться с оператором.\n\nСообщение: {message.text}"
    for admin_id in OPERATOR_CHAT_IDS:
        bot.send_message(admin_id, forward_message)
    bot.send_message(message.chat.id, "Ваше сообщение отправлено операторам. Ожидайте ответа.")
    log_action(message.from_user.id, 'forward_to_operator_main', 'Message to operators')

# Обработка ответов от операторов
@bot.message_handler(func=lambda message: message.chat.id in OPERATOR_CHAT_IDS)
def handle_operator_message(message):
    if hasattr(bot, 'chat_data') and 'user_id' in bot.chat_data:
        user_id = bot.chat_data['user_id']
        original_message_id = bot.chat_data.get('original_message_id', None)

        # Отправка сообщения обратно пользователю
        if original_message_id:
            bot.forward_message(user_id, message.chat.id, message.message_id)
        else:
            bot.send_message(user_id, f"Ответ от оператора:\n\n{message.text}")

        bot.send_message(message.chat.id, "Ваш ответ отправлен пользователю.")
        log_action(message.from_user.id, 'handle_operator_message', f"Message to user ID: {user_id}")
        del bot.chat_data  # Очистка данных после ответа
    else:
        bot.send_message(message.chat.id, "Ошибка: не удалось определить пользователя для ответа.")

@bot.message_handler(commands=['83672064628'])
def send_message(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "Использование: /83672064628 <user_id>")
            return
        user_id = parts[1]
        user_message = "Спасибо, что выбрали именно нас! Вот Ваш готовый курс про перелив трафика из систем:"
        markup = types.InlineKeyboardMarkup()
        web_info = types.WebAppInfo('https://thatsmeee.github.io/finantial/course/course_one/index.html')
        markup.add(types.InlineKeyboardButton("Курс", web_app=web_info))
        bot.send_message(user_id, user_message, reply_markup=markup)
        bot.reply_to(message, "Сообщение успешно отправлено!")
        log_action(message.from_user.id, 'send_message', f"Message sent to user ID: {user_id}")
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {e}")

@bot.message_handler(commands=['320115612'])
def send_message(message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "Использование: /320115612 <user_id> <message>")
            return
        user_id = parts[1]
        user_message = parts[2]
        bot.send_message(user_id, user_message)
        bot.reply_to(message, "Сообщение успешно отправлено!")
        log_action(message.from_user.id, 'send_message', f"Message sent to user ID: {user_id}")
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {e}")

if __name__ == '__main__':
    init_dbs()
    bot.polling(none_stop=True)
