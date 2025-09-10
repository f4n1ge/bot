from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
import sqlite3
import re
import logging
from datetime import datetime

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = '8078259711:AAE8VCU7sZtseyjKOG9N5oYgiizjiGH9iDw'
ADMIN_IDS = [5488211744, 1135087806]
DATABASE_NAME = 'tournaments.db'
SUPPORTED_GAMES = ['Dota 2', 'CS2', 'Fortnite', 'LoL', 'Warface', 'Valorant']

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Подключение к БД
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# ===================== КЛАССЫ СОСТОЯНИЙ ===================== #
class AddTournament(StatesGroup):
    name = State()
    game = State()
    date = State()
    prize = State()
    rules = State()
    max_teams = State()

class EditTournament(StatesGroup):
    select = State()
    field = State()
    value = State()

class RegisterTeam(StatesGroup):
    tournament_id = State()
    team_name = State()
    captain_name = State()
    contact = State()
    players = State()

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===================== #
def admin_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton('Добавить турнир'),
           types.KeyboardButton('Удалить турнир'))
    kb.add(types.KeyboardButton('Редактировать турнир'),
           types.KeyboardButton('Список турниров'))
    kb.add(types.KeyboardButton('Список команд'),
           types.KeyboardButton('Статистика'))
    return kb

def user_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton('Список турниров'),
           types.KeyboardButton('Мои команды'))
    return kb

def cancel_kb():
    return types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton('Отмена'))

def games_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for game in SUPPORTED_GAMES:
        kb.add(types.KeyboardButton(game))
    kb.add(types.KeyboardButton('Отмена'))
    return kb

def get_active_tournaments():
    cursor.execute("SELECT * FROM tournaments WHERE is_active = 1 ORDER BY date")
    return cursor.fetchall()

def get_tournament_by_id(tournament_id):
    cursor.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,))
    return cursor.fetchone()

def get_tournament_teams(tournament_id):
    cursor.execute("SELECT * FROM teams WHERE tournament_id = ?", (tournament_id,))
    return cursor.fetchall()

def get_user_teams(user_id):
    cursor.execute("""
        SELECT t.*, tr.name 
        FROM teams t 
        JOIN tournaments tr ON t.tournament_id = tr.id 
        WHERE t.contact = ? AND tr.is_active = 1
    """, (str(user_id),))
    return cursor.fetchall()

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================== ОСНОВНЫЕ КОМАНДЫ ===================== #
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("👋 Добро пожаловать в админ-панель!", reply_markup=admin_kb())
    else:
        await message.answer(
            "🎮 Добро пожаловать в бота для киберспортивных турниров!\n"
            "Используйте /tournaments для просмотра турниров",
            reply_markup=user_kb()
        )

@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    help_text = """
🤖 <b>Команды бота:</b>

🏆 <b>Для всех пользователей:</b>
/tournaments - Список активных турниров
/my_teams - Мои зарегистрированные команды

⚙️ <b>Для администраторов:</b>
/add_tournament - Добавить турнир
/edit_tournament - Редактировать турнир
/delete_tournament - Удалить турнир
/stats - Статистика
    """
    await message.answer(help_text, parse_mode='HTML')

# ===================== ТУРНИРЫ ===================== #
@dp.message_handler(commands=['tournaments'])
async def show_tournaments(message: types.Message):
    tournaments = get_active_tournaments()
    
    if not tournaments:
        await message.answer("🔍 Сейчас нет активных турниров.")
        return
    
    for tournament in tournaments:
        teams_count = len(get_tournament_teams(tournament[0]))
        
        text = (
            f"🏆 <b>{tournament[1]}</b> ({tournament[2]})\n"
            f"📅 Дата: {tournament[3]}\n"
            f"💰 Приз: {tournament[4]}\n"
            f"👥 Команд: {teams_count}/{tournament[6]}\n"
            f"📌 Правила: {tournament[5][:100]}..." if len(tournament[5]) > 100 else f"📌 Правила: {tournament[5]}"
        )
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            text="Зарегистрироваться", 
            callback_data=f"reg_{tournament[0]}"
        ))
        if is_admin(message.from_user.id):
            kb.add(types.InlineKeyboardButton(
                text="Удалить", 
                callback_data=f"del_{tournament[0]}"
            ))
        
        await message.answer(text, reply_markup=kb, parse_mode='HTML')

@dp.message_handler(lambda message: message.text == 'Список турниров')
async def show_tournaments_button(message: types.Message):
    await show_tournaments(message)

# ===================== АДМИН: ДОБАВЛЕНИЕ ТУРНИРА ===================== #
@dp.message_handler(commands=['add_tournament'])
@dp.message_handler(lambda message: message.text == 'Добавить турнир' and is_admin(message.from_user.id))
async def add_tournament_start(message: types.Message):
    await AddTournament.name.set()
    await message.answer("📝 Введите название турнира:", reply_markup=cancel_kb())

@dp.message_handler(state=AddTournament.name)
async def set_tournament_name(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Добавление турнира отменено.", reply_markup=admin_kb())
        return
    
    await state.update_data(name=message.text)
    await AddTournament.next()
    await message.answer("🎮 Выберите игру:", reply_markup=games_kb())

@dp.message_handler(state=AddTournament.game)
async def set_tournament_game(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Добавление турнира отменено.", reply_markup=admin_kb())
        return
    
    if message.text not in SUPPORTED_GAMES:
        await message.answer("❌ Выберите игру из списка!", reply_markup=games_kb())
        return
    
    await state.update_data(game=message.text)
    await AddTournament.next()
    await message.answer("📅 Введите дату турнира (дд.мм.гггг):", reply_markup=cancel_kb())

@dp.message_handler(state=AddTournament.date)
async def set_tournament_date(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Добавление турнира отменено.", reply_markup=admin_kb())
        return
    
    if not re.match(r'\d{2}\.\d{2}\.\d{4}', message.text):
        await message.answer("❌ Неверный формат даты! Используйте дд.мм.гггг")
        return
    
    await state.update_data(date=message.text)
    await AddTournament.next()
    await message.answer("💰 Введите призовой фонд:", reply_markup=cancel_kb())

@dp.message_handler(state=AddTournament.prize)
async def set_tournament_prize(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Добавление турнира отменено.", reply_markup=admin_kb())
        return
    
    await state.update_data(prize=message.text)
    await AddTournament.next()
    await message.answer("📜 Введите правила турнира:", reply_markup=cancel_kb())

@dp.message_handler(state=AddTournament.rules)
async def set_tournament_rules(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Добавление турнира отменено.", reply_markup=admin_kb())
        return
    
    await state.update_data(rules=message.text)
    await AddTournament.next()
    await message.answer("👥 Введите максимальное количество команд:", reply_markup=cancel_kb())

@dp.message_handler(state=AddTournament.max_teams)
async def set_tournament_max_teams(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Добавление турнира отменено.", reply_markup=admin_kb())
        return
    
    try:
        max_teams = int(message.text)
        if max_teams <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число!")
        return
    
    data = await state.get_data()
    cursor.execute(
        "INSERT INTO tournaments (name, game, date, prize, rules, max_teams) VALUES (?, ?, ?, ?, ?, ?)",
        (data['name'], data['game'], data['date'], data['prize'], data['rules'], max_teams)
    )
    conn.commit()
    
    await message.answer(
        f"✅ Турнир <b>{data['name']}</b> успешно добавлен!",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )
    await state.finish()

# ===================== АДМИН: УДАЛЕНИЕ ТУРНИРА ===================== #
@dp.message_handler(commands=['delete_tournament'])
@dp.message_handler(lambda message: message.text == 'Удалить турнир' and is_admin(message.from_user.id))
async def delete_tournament_start(message: types.Message):
    tournaments = get_active_tournaments()
    
    if not tournaments:
        await message.answer("🔍 Нет активных турниров для удаления.")
        return
    
    kb = types.InlineKeyboardMarkup()
    for tournament in tournaments:
        kb.add(types.InlineKeyboardButton(
            text=f"{tournament[1]} ({tournament[2]})", 
            callback_data=f"del_{tournament[0]}"
        ))
    
    await message.answer("🗑 Выберите турнир для удаления:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('del_'))
async def process_delete_tournament(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Нет прав доступа!")
        return
    
    tournament_id = int(callback.data.split('_')[1])
    cursor.execute("UPDATE tournaments SET is_active = 0 WHERE id = ?", (tournament_id,))
    conn.commit()
    
    # Удаляем все команды этого турнира
    cursor.execute("DELETE FROM teams WHERE tournament_id = ?", (tournament_id,))
    conn.commit()
    
    await callback.message.edit_text("✅ Турнир успешно удален.")
    await callback.answer()

# ===================== АДМИН: РЕДАКТИРОВАНИЕ ТУРНИРА ===================== #
@dp.message_handler(commands=['edit_tournament'])
@dp.message_handler(lambda message: message.text == 'Редактировать турнир' and is_admin(message.from_user.id))
async def edit_tournament_start(message: types.Message):
    tournaments = get_active_tournaments()
    
    if not tournaments:
        await message.answer("🔍 Нет активных турниров для редактирования.")
        return
    
    kb = types.InlineKeyboardMarkup()
    for tournament in tournaments:
        kb.add(types.InlineKeyboardButton(
            text=f"{tournament[1]} ({tournament[2]})", 
            callback_data=f"edit_{tournament[0]}"
        ))
    
    await EditTournament.select.set()
    await message.answer("✏️ Выберите турнир для редактирования:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('edit_'), state=EditTournament.select)
async def select_tournament_to_edit(callback: types.CallbackQuery, state: FSMContext):
    tournament_id = int(callback.data.split('_')[1])
    await state.update_data(tournament_id=tournament_id)
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton('Название'),
           types.KeyboardButton('Дата'))
    kb.add(types.KeyboardButton('Приз'),
           types.KeyboardButton('Правила'))
    kb.add(types.KeyboardButton('Макс. команд'),
           types.KeyboardButton('Отмена'))
    
    await EditTournament.field.set()
    await callback.message.answer("📌 Выберите поле для редактирования:", reply_markup=kb)
    await callback.answer()

@dp.message_handler(state=EditTournament.field)
async def select_field_to_edit(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Редактирование отменено.", reply_markup=admin_kb())
        return
    
    valid_fields = ['Название', 'Дата', 'Приз', 'Правила', 'Макс. команд']
    if message.text not in valid_fields:
        await message.answer("❌ Выберите поле из списка!")
        return
    
    await state.update_data(field=message.text)
    await EditTournament.value.set()
    await message.answer(f"✏️ Введите новое значение для '{message.text}':", reply_markup=cancel_kb())

@dp.message_handler(state=EditTournament.value)
async def set_new_value(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Редактирование отменено.", reply_markup=admin_kb())
        return
    
    data = await state.get_data()
    field = data['field']
    tournament_id = data['tournament_id']
    
    # Валидация данных
    if field == 'Макс. команд':
        try:
            value = int(message.text)
            if value <= 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введите положительное число!")
            return
    elif field == 'Дата':
        if not re.match(r'\d{2}\.\d{2}\.\d{4}', message.text):
            await message.answer("❌ Неверный формат даты! Используйте дд.мм.гггг")
            return
        value = message.text
    else:
        value = message.text
    
    # Обновление в БД
    db_fields = {
        'Название': 'name',
        'Дата': 'date',
        'Приз': 'prize',
        'Правила': 'rules',
        'Макс. команд': 'max_teams'
    }
    
    cursor.execute(
        f"UPDATE tournaments SET {db_fields[field]} = ? WHERE id = ?",
        (value, tournament_id)
    )
    conn.commit()
    
    await message.answer(
        f"✅ Поле '{field}' успешно обновлено!",
        reply_markup=admin_kb()
    )
    await state.finish()

# ===================== РЕГИСТРАЦИЯ КОМАНД ===================== #
@dp.callback_query_handler(lambda c: c.data.startswith('reg_'))
async def register_team_start(callback: types.CallbackQuery, state: FSMContext):
    tournament_id = int(callback.data.split('_')[1])
    tournament = get_tournament_by_id(tournament_id)
    
    if not tournament:
        await callback.answer("❌ Турнир не найден!")
        return
    
    teams = get_tournament_teams(tournament_id)
    if len(teams) >= tournament[6]:
        await callback.answer("❌ Набрано максимальное количество команд!")
        return
    
    # Проверка существующей регистрации
    user_teams = get_user_teams(callback.from_user.id)
    for team in user_teams:
        if team[1] == tournament_id:
            await callback.answer("❌ Вы уже зарегистрированы на этот турнир!")
            return
    
    await state.set_state(RegisterTeam.tournament_id)
    await state.update_data(tournament_id=tournament_id)
    
    await callback.message.answer(
        f"🏆 Регистрация на турнир: <b>{tournament[1]}</b>\n"
        "📝 Введите название команды:",
        reply_markup=cancel_kb(),
        parse_mode='HTML'
    )
    await callback.answer()

@dp.message_handler(state=RegisterTeam.team_name)
async def set_team_name(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    await state.update_data(team_name=message.text)
    await RegisterTeam.next()
    await message.answer("👤 Введите имя капитана:", reply_markup=cancel_kb())

@dp.message_handler(state=RegisterTeam.captain_name)
async def set_captain_name(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    await state.update_data(captain_name=message.text)
    await RegisterTeam.next()
    await message.answer("📱 Введите контакт для связи:", reply_markup=cancel_kb())

@dp.message_handler(state=RegisterTeam.contact)
async def set_contact(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    await state.update_data(contact=message.text)
    await RegisterTeam.next()
    await message.answer("👥 Введите состав команды (никнеймы через запятую):", reply_markup=cancel_kb())

@dp.message_handler(state=RegisterTeam.players)
async def set_players(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.finish()
        await message.answer("❌ Регистрация отменена.", reply_markup=types.ReplyKeyboardRemove())
        return
    
    data = await state.get_data()
    cursor.execute(
        "INSERT INTO teams (tournament_id, team_name, captain_name, contact, players) VALUES (?, ?, ?, ?, ?)",
        (data['tournament_id'], data['team_name'], data['captain_name'], data['contact'], message.text)
    )
    conn.commit()
    
    tournament = get_tournament_by_id(data['tournament_id'])
    await message.answer(
        f"✅ Ваша команда <b>{data['team_name']}</b> успешно зарегистрирована на турнир <b>{tournament[1]}</b>!\n"
        f"📅 Дата: {tournament[3]}\n"
        f"📜 Правила: {tournament[5]}",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode='HTML'
    )
    await state.finish()

# ===================== МОИ КОМАНДЫ ===================== #
@dp.message_handler(commands=['my_teams'])
@dp.message_handler(lambda message: message.text == 'Мои команды')
async def show_my_teams(message: types.Message):
    teams = get_user_teams(message.from_user.id)
    
    if not teams:
        await message.answer("🔍 У вас нет зарегистрированных команд.")
        return
    
    response = "👥 <b>Ваши зарегистрированные команды:</b>\n\n"
    for team in teams:
        tournament = get_tournament_by_id(team[1])
        response += (
            f"🏆 Турнир: {tournament[1]}\n"
            f"🏷 Команда: {team[2]}\n"
            f"👤 Капитан: {team[3]}\n"
            f"👥 Состав: {team[5]}\n\n"
        )
    
    await message.answer(response, parse_mode='HTML')

# ===================== АДМИН: СПИСОК КОМАНД ===================== #
@dp.message_handler(lambda message: message.text == 'Список команд' and is_admin(message.from_user.id))
async def show_all_teams(message: types.Message):
    cursor.execute("""
        SELECT t.id, tr.name, t.team_name, t.captain_name, t.players 
        FROM teams t 
        JOIN tournaments tr ON t.tournament_id = tr.id
        WHERE tr.is_active = 1
    """)
    teams = cursor.fetchall()
    
    if not teams:
        await message.answer("🔍 Нет зарегистрированных команд.")
        return
    
    response = "👥 <b>Список всех команд:</b>\n\n"
    for team in teams:
        response += (
            f"🏆 Турнир: {team[1]}\n"
            f"🏷 Команда: {team[2]}\n"
            f"👤 Капитан: {team[3]}\n"
            f"👥 Состав: {team[4]}\n\n"
        )
    
    await message.answer(response, parse_mode='HTML')

# ===================== СТАТИСТИКА ===================== #
@dp.message_handler(commands=['stats'])
@dp.message_handler(lambda message: message.text == 'Статистика' and is_admin(message.from_user.id))
async def show_stats(message: types.Message):
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM tournaments WHERE is_active = 1")
    active_tournaments = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM teams")
    total_teams = cursor.fetchone()[0]
    
    # Статистика по играм
    cursor.execute("""
        SELECT game, COUNT(*) as count 
        FROM tournaments 
        WHERE is_active = 1 
        GROUP BY game
    """)
    games_stats = cursor.fetchall()
    
    # Статистика по командам в турнирах
    cursor.execute("""
        SELECT t.name, COUNT(te.id) as team_count
        FROM tournaments t
        LEFT JOIN teams te ON t.id = te.tournament_id
        WHERE t.is_active = 1
        GROUP BY t.id
    """)
    tournament_stats = cursor.fetchall()
    
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"🏆 Активных турниров: {active_tournaments}\n"
        f"👥 Всего команд: {total_teams}\n\n"
        f"🎮 По играм:\n"
    )
    
    for game, count in games_stats:
        text += f"• {game}: {count} турниров\n"
    
    text += f"\n📈 По турнирам:\n"
    for tournament_name, team_count in tournament_stats:
        text += f"• {tournament_name}: {team_count} команд\n"
    
    await message.answer(text, parse_mode='HTML')

# ===================== ОБРАБОТКА НЕИЗВЕСТНЫХ КОМАНД ===================== #
@dp.message_handler()
async def unknown_command(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("🤔 Неизвестная команда. Используйте кнопки меню.", reply_markup=admin_kb())
    else:
        await message.answer("🤔 Неизвестная команда. Используйте /help для списка команд.", reply_markup=user_kb())

# ===================== ЗАПУСК БОТА ===================== #
if __name__ == '__main__':
    try:
        # Создание таблиц при первом запуске
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            game TEXT NOT NULL,
            date TEXT NOT NULL,
            prize TEXT,
            rules TEXT,
            max_teams INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER,
            team_name TEXT NOT NULL,
            captain_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            players TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES tournaments (id)
        )
        ''')
        conn.commit()
        
        logger.info("Бот запущен")
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        conn.close()
        logger.info("Бот остановлен")