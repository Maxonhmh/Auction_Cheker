import asyncio
import logging
import pymysql
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters.command import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from api_conector import main_1

from api_conector import clear_table

from name_id import item_name_id

from DB_CONFIG import DB_CONFIG_sub




from datetime import datetime

logging.basicConfig(level=logging.INFO)

bot = Bot(token="7800360923:AAF2UurihkKuAggzy94Q4w3-eC16B1Ob7vs")
dp = Dispatcher()
router = Router()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

item_name_to_id = item_name_id




monitoring_active = False



user_alerts = {}

DB_CONFIG = DB_CONFIG_sub


def get_lots_below_price(target_price, item_identifier=None):
    logging.info(f"Connecting to database with target price {target_price} and item_identifier {item_identifier}...")
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT DISTINCT item_name, buyout_price, start_time, end_time
                FROM item_details
                WHERE buyout_price <= %s AND buyout_price >= 1
            """

            if item_identifier:
                if item_identifier in item_name_to_id:
                    item_name = item_name_to_id[item_identifier]
                    query += " AND item_name LIKE %s"
                    cursor.execute(query, (target_price, f"%{item_name}%"))
                elif item_identifier.isdigit():  # Если передан числовой ID
                    query += " AND item_id = %s"
                    cursor.execute(query, (target_price, item_identifier))
                else:
                    logging.warning(f"Не удалось найти предмет с идентификатором {item_identifier}")
            else:
                cursor.execute(query, (target_price,))

            query += " ORDER BY buyout_price ASC LIMIT 10"
            

            cursor.execute(query, (target_price,))
            results = cursor.fetchall()
            logging.info(f"Query returned {len(results)} results: {results}")

            formatted_results = []
            for result in results:
                item_name_db = result[0]
                buyout_price = result[1]
                start_time = result[2]
                end_time = result[3]

                start_time_str = datetime.strptime(str(start_time), '%Y-%m-%d %H:%M:%S') if start_time else "N/A"
                end_time_str = datetime.strptime(str(end_time), '%Y-%m-%d %H:%M:%S') if end_time else "N/A"
                
                formatted_results.append({
                    "item_name": item_name_db,
                    "buyout_price": buyout_price,
                    "start_time": start_time_str,
                    "end_time": end_time_str
                })
            
            return formatted_results
    finally:
        connection.close()



@router.message(Command("start"))
async def start_command(message: types.Message):
    btn2 = InlineKeyboardButton(text="Установить цену", callback_data="set_price")
    btn1 = InlineKeyboardButton(text="установить название", callback_data="set_name")
    btn3 = InlineKeyboardButton(text="начать мониторинг", callback_data="notify_users1")
    row1 = [btn1, btn2]
    row2 = [btn3] 
    rows = [row1, row2]
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        "Добро пожаловать! Укажите целевую цену, чтобы получать уведомления о лотах.",
        reply_markup=markup
    )


@router.callback_query(F.data == "set_price")
async def set_price(callback: CallbackQuery):
    await callback.message.answer(
        "Пожалуйста, отправьте сообщение с целевой ценой в формате: 50000"
    )
    await callback.answer()


@router.callback_query(F.data == "set_name")
async def set_name(callback: CallbackQuery):
    await callback.message.answer(
        "Пожалуйста, отправьте сообщение с названием предмета или его id"
    )
    await callback.answer()



@router.message(F.text.regexp(r'^\d+$'))
async def receive_price(message: types.Message):
    user_id = message.from_user.id
    target_price = int(message.text)
    if user_id not in user_alerts:
        user_alerts[user_id] = {'price': target_price } 
    else:    
        user_alerts[user_id]['price'] = target_price
    await message.answer(f"Целевая цена установлена: {target_price}")
    await start_command(message)




@router.message(F.text.regexp(r'^\w+$')) 
async def receive_item_id(message: types.Message):
    user_id = message.from_user.id
    item_id = message.text.strip()
    if item_id in item_name_to_id:  
        item_name = item_name_to_id[item_id] 
        await message.answer(f"Предмет с ID {item_id} найден, его название: {item_name}.")
        await start_command(message)

        user_alerts[user_id]['name'] = item_name 
    else:
        await message.answer(f"Предмет с ID {item_id} не найден в списке соответствий.")
        await start_command(message)
    user_alerts[user_id]['id'] = item_id
    await start_command(message)




@router.message(F.text.regexp(r'^[\w\sа-яА-ЯёЁ]+$'))  
async def receive_item_name(message: types.Message):
    user_id = message.from_user.id
    item_name = message.text.strip().lower()
    item_id = None
    for key, value in item_name_to_id.items():
        if value.lower() == item_name.lower():
            item_id = key
            break

    if item_id:
        await message.answer(f"Предмет {item_name} имеет ID {item_id}.")
        user_alerts[user_id]['name'] = item_name  
    else:
        await message.answer(f"Предмет с названием {item_name} не найден.")
    
    await start_command(message)

@router.callback_query(F.data == "stop_monitoring")
async def stop_monitoring(callback: CallbackQuery):
    global monitoring_active
    monitoring_active = False 
    await callback.message.answer("Мониторинг остановлен.")
    await callback.answer()
    await start_command(callback.message)




@router.callback_query(F.data == "notify_users1")
async def start_monitoring(callback: CallbackQuery):
    await callback.message.answer("Запуск мониторинга...")
    global monitoring_active
    monitoring_active = True
    await notify_users()

    await callback.answer()

async def notify_users():
    """Проверка базы данных и уведомление пользователей о подходящих лотах."""
    if not monitoring_active:  
        logging.info("Мониторинг остановлен, завершение работы функции.")
        return
    for user_id, alert in user_alerts.items():
        target_price = alert['price']
        item_name = alert.get('name', None)
        lots = get_lots_below_price(target_price, item_name)
        if lots:
            message = "Найдены подходящие лоты:\n"
            for lot in lots:
                lot_info = f"Название: {lot['item_name']}, Цена: {lot['buyout_price']}, " \
                           f"Начало: {lot['start_time']}, Конец: {lot['end_time']}\n"
                message += lot_info
            if message.strip() != "Найдены подходящие лоты:\n":
                btn5 = InlineKeyboardButton(text="остановить мониторинг", callback_data="stop_monitoring")
                row51 = [btn5]
                rows51 = [row51]
                markup = InlineKeyboardMarkup(inline_keyboard=rows51)
                await bot.send_message(user_id, message, reply_markup=markup)


async def refrsh():
    clear_table()
    main_1()


scheduler.add_job(notify_users, "interval", minutes=0.1)

scheduler.add_job(refrsh, "interval", minutes=0.5)   


async def main():
    dp.include_router(router)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
