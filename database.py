from datetime import datetime, timedelta
import sqlite3
from sqlite3 import Error

from secrets import BOT_TAG, TO_ACHIEVE_GOLD_STATUS, TO_ACHIEVE_PLATINA_STATUS


def create_connection(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()


def create_table(con, name):
    with con:
        if name == "users":
            con.execute('''CREATE TABLE IF NOT EXISTS users
                         (id integer PRIMARY KEY, telegram_id text, balance bigint, status text, 
                         is_follower int, invited_by text, q_of_trades bigint, earned_from_partnership bigint)''')
        elif name == 'requests':
            con.execute('''CREATE TABLE IF NOT EXISTS requests
                                 (id integer PRIMARY KEY, telegram_id text, status text, 
                                 type text, when_created text, comment text, wallet text)''')
        con.commit()


def get_request_by_telegram_id(conn, telegram_id: int, rq_type='trade', status='any'):
    with conn:
        telegram_id = int(telegram_id)
        cur = conn.cursor()
        cur.execute("SELECT * FROM requests")
        rows = cur.fetchall()
        if status == 'any':
            for row in rows:
                rq_status = row[2]
                if int(row[1]) == telegram_id and rq_type in row[3] and rq_status != "user_confirmed" \
                        and rq_status != 'T: user_payed':
                    return list(row)
        else:
            for row in rows:
                if int(row[1]) == telegram_id and rq_type in row[3]:
                    return list(row)
    return None


def get_request_by_id(conn, rq_id: int):
    rq_id = int(rq_id)
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM requests")
        rows = cur.fetchall()
        for row in rows:
            if row[0] == rq_id:
                return list(row)
        return None


def add_request_to_db(conn, request):
    request_type = request[3]
    user_id = request[0]
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, telegram_id, type, status FROM requests")
        res = cursor.fetchall()

        for r in res:
            if r[1] == user_id and r[2] == request_type and r[3] != 'user_confirmed' and r[3] != 'T: user_payed':
                print(request, 'founded instead of adding new')
                request = get_request_by_telegram_id(conn, user_id, rq_type=request_type)
                return request

        sql = f''' INSERT INTO requests(telegram_id, status, type, when_created, comment, wallet)
                                                     VALUES(?,?,?,?,?,?) '''
        cursor.execute(sql, request)
        conn.commit()
        print(get_request_by_telegram_id(conn, user_id, rq_type=request_type), 'added', request_type)
        return get_request_by_telegram_id(conn, user_id, rq_type=request_type)


def unreplenish_user_balance(c, client_id, amount: (int or float), ):
    user = get_user_by_telegram_id(c, client_id)
    if (float(user[2]) - float(amount)) < 0:
        user[2] = float(user[2]) - float(amount)
        update_user_in_db(c, user)
        return True
    else:
        return False


def replenish_user_balance(c, client_id, amount: (int or float)):
    user = get_user_by_telegram_id(c, client_id)
    user[2] = float(user[2]) + float(amount)
    update_user_in_db(c, user)


def user_in_db(c, client_id):
    if get_user_by_telegram_id(c, telegram_id=client_id) is not None:
        return True
    return False


def get_status_message(c, call):
    call_data, request_id, client_id, status = call.data.split(" ")
    if status in ["no_payment", 'close_request']:
        delete_request_from_db(c, request_id)
    status_msgs = {'payment_s': 'Платёж подтверждён!',
                   'crypto_sent': 'Криптовалюта отправлена!',
                   'replenish_s': 'Баланс пополнен!',
                   'not_enough': 'Было отправленно недостаточно средств!',
                   'no_payment': "Не удалось найти ваш платёж!",
                   'close_request': 'Заявка закрыта!'}
    message = status_msgs[status]
    return client_id, message


def update_user_in_db(conn, usr):
    user_id = usr[1]
    with conn:
        cursor = conn.cursor()
        cursor.execute(f'UPDATE users SET id = ?, telegram_id = ?, balance = ?, status = ?, '
                       f'is_follower = ?, invited_by = ?, '
                       f'q_of_trades = ?, earned_from_partnership = ? WHERE telegram_id = {user_id}', usr)
        conn.commit()
    print(get_user_by_telegram_id(conn, user_id), 'usr updated')


def update_request_in_db(conn, rq):
    request_id = rq[0]
    with conn:
        cursor = conn.cursor()
        cursor.execute(f'UPDATE requests SET id = ?, telegram_id = ?, status = ?, type = ?, '
                       f'when_created = ?, comment = ?, wallet = ? WHERE id = {request_id}', rq)
        conn.commit()
    print(get_request_by_id(conn, request_id), 'rq updated')


def get_requests(c, user_id):
    trade_request = get_request_by_telegram_id(c, user_id)
    help_request = get_request_by_telegram_id(c, user_id, rq_type='help_request')
    replenish_request = get_request_by_telegram_id(c, user_id, rq_type='replenish')
    service_request = get_request_by_telegram_id(c, user_id, rq_type='service_request')
    return_request = get_request_by_telegram_id(c, user_id, rq_type='return')
    return trade_request, help_request, replenish_request, service_request, return_request


def delete_request_from_db(conn, request_id: int):
    request_id = str(request_id)
    with conn:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM requests WHERE id = {request_id}')
        conn.commit()


def select_all_requests(conn):
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM requests")

        rows = cur.fetchall()

        for row in rows:
            print(row)
        return rows


def request_time_is_done(request_time):
    # 2020-08-06 18:33:02.276834
    tdelta = timedelta(hours=1)
    now = datetime.now()

    return request_time < str(now - tdelta)


def get_partnership_text(c, user_id):
    user = get_user_by_telegram_id(c, user_id)
    invited_by_user = get_number_of_invitations(c, user_id)
    referal_code = hex(user_id)
    partnership_link = fr'https://t.me/{BOT_TAG}?start={referal_code}'
    text = f'''
👥 👥 0.3% от суммы выданной валюты
🤝 Приглашено пользователей: {invited_by_user}
💰 Заработано: {user[7]} руб.
💳 Доступно на вывод: {user[2]} руб.
* для вывода обращайтесь в тех. поддержку
➖➖➖➖➖➖➖➖
🔗 Ваша партнерская ссылка:
{partnership_link}'''
    return text


def raise_users_q_of_trades(c, client_id):
    user = get_user_by_telegram_id(c, telegram_id=client_id)
    if user is not None:
        user[6] = int(user[6]) + 1
        if user[6] == TO_ACHIEVE_GOLD_STATUS:
            user[3] = 'Золотой'
        elif user[6] == TO_ACHIEVE_PLATINA_STATUS:
            user[3] = 'Платина'
        update_user_in_db(c, user)
    else:
        print('user not found')


def check_requests_shell_life(conn):
    requests = select_all_requests(conn)
    for r in requests:
        user_id = r[1]
        request_time = r[4]
        request_type = r[3]
        request_status = r[2]
        if request_time_is_done(request_time) and request_type != 'help_request' \
                and request_status != 'user_confirmed' \
                and request_status != 'T: user_payed':
            delete_request_from_db(conn, user_id)


def add_new_user_to_db(conn, user_id, follow_status, invited_by):
    user = [user_id, 0, 'Серебрянный', follow_status, invited_by, 0, 0]
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id FROM users")
        res = cursor.fetchall()

        if res is None or get_user_by_telegram_id(conn, user[0]) is None:
            sql = f'INSERT INTO users(telegram_id, balance, status, is_follower, invited_by, ' \
                  f'q_of_trades, earned_from_partnership) VALUES(?,?,?,?,?,?,?)'
            cursor.execute(sql, user)
            conn.commit()
            return user

        else:
            user = get_user_by_telegram_id(conn, user[0])
            return user


def select_all_users(conn):
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users")

        rows = cur.fetchall()

        for row in rows:
            print(row)
        return rows


def get_all_requests_in_list(conn) -> list:
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM requests")

        rows = cur.fetchall()
        requests = []
        for row in rows:
            if row[2] == "user_confirmed" or row[2] == 'user_payed':
                requests.append(row)

    return requests


def get_user_by_telegram_id(conn, telegram_id: int):
    """:param conn: the Connection object
        :param telegram_id: str telegram_id """
    telegram_id = int(telegram_id)
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()
        for row in rows:
            if int(row[1]) == telegram_id:
                return list(row)
    return None


def get_number_of_invitations(conn, user_id):
    with conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM users WHERE invited_by = ({user_id})")
        res = cur.fetchall()
        print(res)
        number = len(res)
        return number


def pay_inviter(c, client_id, fee):
    user = get_user_by_telegram_id(c, client_id)
    inviter_id = user[5]
    if inviter_id != 'None':
        inviter = get_user_by_telegram_id(c, inviter_id)
        inviter[7] = inviter[7] + fee  # earned from partnership increased
        inviter[2] = inviter[2] + fee  # balance increased
        update_user_in_db(c, inviter)


if __name__ == '__main__':
    c = sqlite3.connect('database.db')
    select_all_users(c)
    print('_' * 100)
    select_all_requests(c)
