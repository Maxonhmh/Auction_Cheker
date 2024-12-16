import requests
from multiprocessing import Pool
import time
from all_items import ALL_Unik_items
import pymysql
from datetime import datetime


from api_config import client_id_CFG
from api_config import client_secret_CFG
from api_config import access_token_CFG

client_id = client_id_CFG
client_secret = client_secret_CFG 
token_url =  "https://exbo.net/oauth/token" 
access_token = access_token_CFG
# Данные авторизации

important_item = ['4q7pl','y3nmw']

# Заголовки с токеном
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {access_token}"  # Bearer-токен
}

# Функция для подключения к базе данных
def connect_to_db():
    try:
        connection = pymysql.connect(
            host="localhost",         # Используй localhost или 127.0.0.1
            user="root",              # Твой пользователь
            password="root",          # Твой пароль
            database="stalcraft"      # Имя базы данных
        )
        print("Успешное подключение к базе данных")
        return connection
    except pymysql.MySQLError as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

# Функция для добавления предмета в таблицу items
def add_item(cursor, item_name):
    cursor.execute("SELECT name FROM items WHERE name = %s", (item_name,))
    result = cursor.fetchone()
    if not result:
        cursor.execute("INSERT INTO items (name) VALUES (%s)", (item_name,))


# Функция для добавления деталей предмета
def add_item_details(cursor, item_name, amount, start_price, buyout_price, start_time, end_time):
    cursor.execute(
        """
        INSERT INTO item_details (item_name, amount, start_price, buyout_price, start_time, end_time)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (item_name, amount, start_price, buyout_price, start_time, end_time)
    )



def format_datetime(mysql_datetime_str):
    return datetime.strptime(mysql_datetime_str, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")


# Функция для обработки одного предмета
def process_item(item):
    local_headers = headers.copy()
    url_item = f"https://eapi.stalcraft.net/ru/auction/{item}/lots"
    max_retries = 2
    retry_delay = 1
    attempt = 0

    while attempt < max_retries:
        try:
            response = requests.get(url_item, headers=local_headers)
            if response.status_code == 200:
                data = response.json()
                lots = data.get("lots", [])
                if not lots:
                    print(f"Нет доступных лотов для {item}")
                    return

                connection = connect_to_db()
                if not connection:
                    return

                cursor = connection.cursor()

                for lot in lots:
                    lot["startTime"] = format_datetime(lot["startTime"])
                    lot["endTime"] = format_datetime(lot["endTime"])

                    # Добавляем детали предмета в таблицу
                    add_item_details(
                        cursor,
                        f"{item}",  # Имя предмета
                        lot["amount"],
                        lot["startPrice"],
                        lot["buyoutPrice"],
                        lot["startTime"],
                        lot["endTime"]
                    )

                connection.commit()
                connection.close()
                print(f"Данные для предмета {item} успешно добавлены в базу данных.")
                return
            else:
                print(f"Ошибка {response.status_code} для {item}. Ответ от сервера: {response.text}")
        except Exception as e:
            print(f"Ошибка при обработке {item}: {e}.")
        attempt += 1
        time.sleep(retry_delay)
    print(f"Не удалось обработать {item} после {max_retries} попыток.")




def show_all_data():
    """Вывод всех данных из базы данных."""
    connection = connect_to_db()
    if not connection:
        return

    cursor = connection.cursor()
    try:
        print("\nТаблица item_details:")
        cursor.execute("SELECT * FROM item_details")
        details = cursor.fetchall()
        for detail in details:
            print(detail)
    except pymysql.MySQLError as e:
        print(f"Ошибка при чтении данных: {e}")
    finally:
        cursor.close()
        connection.close()

def clear_table():
    connection = connect_to_db()
    if not connection:
        return
    
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM item_details")
        cursor.execute("TRUNCATE TABLE item_details")
        connection.commit()
        print("Таблица item_details успешно очищена.")
    except pymysql.MySQLError as e:
        print(f"Ошибка при очистке таблицы: {e}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()



# Главная функция
def main_1():
    important_item = ['4q7pl','y3nmw']  # Пример списка предметов

    with Pool(processes=3) as pool:  # Количество процессов можно настроить
        pool.map(process_item, important_item)

    print("Парсинг и добавление данных завершены.")

if __name__ == "__main__":
    clear_table()  # Очистка таблиц
    main_1()          # Добавление новых данных
    print("\nВывод всех данных из базы:")
    show_all_data()
