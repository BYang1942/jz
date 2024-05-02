import sqlite3
import datetime
import schedule
import time
import telebot
from telebot import types
import re  # 添加这一行
from config import TOKEN, ADMIN_ID

bot = telebot.TeleBot(TOKEN)

authorized_users = {ADMIN_ID}

def create_tables():
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS accounts
        (group_id INTEGER,
        user_id INTEGER,
        balance REAL,
        deposit REAL,
        withdraw REAL,
        PRIMARY KEY (group_id, user_id))
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions
        (group_id INTEGER,
        user_id INTEGER,
        time TEXT,
        amount REAL)
    ''')
    conn.commit()
    conn.close()

create_tables()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton('福利来官方频道', url='https://t.me/FLLG1')
    # btn2 = types.InlineKeyboardButton('点击这里把我添加进群组', url='https://t.me/x_dbbot?startgroup=true')
    # btn3 = types.InlineKeyboardButton('官方频道', url='https://t.me/aaaaaaaaaa666666666666666666')
    keyboard.add(btn1, btn2, btn3)
    bot.send_message(message.chat.id, "您好，我可以为您记账，请称呼我为记账小助手！很高兴认识您~", reply_markup=keyboard)

# 全局费率
global_rate = 0.0

# 创建全局账户
def create_global_account(group_id):
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    c.execute('SELECT * FROM accounts WHERE user_id = -1 AND group_id = ?', (group_id,))  # 使用-1作为全局账户的user_id
    if c.fetchone() is None:
        c.execute('INSERT INTO accounts VALUES (?, -1, 0, 0, 0)', (group_id,))
    conn.commit()
    conn.close()


@bot.message_handler(func=lambda message: message.text.startswith("设置管理") and message.from_user.id == ADMIN_ID)
def add_admin(message):
    try:
        new_admin_id = int(message.text.split()[1])
        authorized_users.add(new_admin_id)
        bot.send_message(message.chat.id, f"用户 {new_admin_id} 已被设置为管理员。")
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "命令格式错误。请使用 '设置管理 用户ID'。")

@bot.message_handler(func=lambda message: message.text.startswith("取消管理") and message.from_user.id == ADMIN_ID)
def remove_admin(message):
    try:
        admin_id = int(message.text.split()[1])
        if admin_id in authorized_users:
            authorized_users.remove(admin_id)
            bot.send_message(message.chat.id, f"用户 {admin_id} 的管理员权限已被取消。")
        else:
            bot.send_message(message.chat.id, f"用户 {admin_id} 不是管理员。")
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "命令格式错误。请使用 '取消管理 用户ID'。")



@bot.message_handler(func=lambda message: message.text == "撤销入款" and message.from_user.id in authorized_users)
def undo_last_deposit(message):
    print("Received undo command")  # 确认消息处理器被触发
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    group_id = message.chat.id  # 获取群组 ID

    try:
        # 获取最后一笔入款记录
        c.execute('SELECT * FROM transactions WHERE group_id = ? AND amount > 0 ORDER BY time DESC LIMIT 1', (group_id,))
        last_deposit = c.fetchone()

        # 打印查询结果
        print("Last deposit:", last_deposit)

        if last_deposit is None:
            bot.send_message(message.chat.id, "没有找到入款记录。")
            return

        # 删除最后一笔入款记录
        c.execute('DELETE FROM transactions WHERE group_id = ? AND time = ? AND amount = ?', (group_id, last_deposit[2], last_deposit[3]))

        # 更新全局账户余额
        c.execute('UPDATE accounts SET balance = balance - ? WHERE user_id = -1 AND group_id = ?', (last_deposit[3], group_id))

        conn.commit()
        bot.send_message(message.chat.id, "最后一笔入款记录已被撤销。")
    except sqlite3.Error as error:
        print("Error while executing sqlite3 query:", error)
        bot.send_message(message.chat.id, "撤销入款时发生错误。")
    finally:
        conn.close()


@bot.message_handler(func=lambda message: message.text == "撤销下发" and message.from_user.id in authorized_users)
def undo_last_withdraw(message):
    print("Received undo command")  # 确认消息处理器被触发
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    group_id = message.chat.id  # 获取群组 ID

    try:
        # 获取最后一笔下发记录
        c.execute('SELECT * FROM transactions WHERE group_id = ? AND amount < 0 ORDER BY time DESC LIMIT 1', (group_id,))
        last_withdraw = c.fetchone()

        # 打印查询结果
        print("Last withdraw:", last_withdraw)

        if last_withdraw is None:
            bot.send_message(message.chat.id, "没有找到下发记录。")
            return

        # 删除最后一笔下发记录
        c.execute('DELETE FROM transactions WHERE group_id = ? AND time = ? AND amount = ?', (group_id, last_withdraw[2], last_withdraw[3]))

        # 更新全局账户余额
        c.execute('UPDATE accounts SET balance = balance - ? WHERE user_id = -1 AND group_id = ?', (last_withdraw[3], group_id))

        conn.commit()
        bot.send_message(message.chat.id, "最后一笔下发记录已被撤销。")
    except sqlite3.Error as error:
        print("Error while executing sqlite3 query:", error)
        bot.send_message(message.chat.id, "撤销下发时发生错误。")
    finally:
        conn.close()


@bot.message_handler(func=lambda message: message.text.startswith('设置费率 ') and message.from_user.id in authorized_users)
def set_rate(message):
    global global_rate
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].replace('.', '', 1).isdigit():
        bot.send_message(message.chat.id, "无效的费率格式。请使用 '设置费率 数值'。")
        return
    global_rate = float(parts[1]) * 0.01  # 将输入的数值转换为百分比
    group_id = message.chat.id  # 获取群组 ID
    create_global_account(group_id)  # 创建全局账户
    bot.send_message(message.chat.id, "费率已设置为 {:.2%}。".format(global_rate))  # 使用 {:.2%} 来格式化输出百分比


# 全局汇率
exchange_rate = 7.0

@bot.message_handler(func=lambda message: message.text.startswith('设置汇率 ') and message.from_user.id in authorized_users)
def set_exchange_rate(message):
    global exchange_rate
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].replace('.', '', 1).isdigit():
        bot.send_message(message.chat.id, "无效的汇率格式。请使用 '设置汇率 数值'。")
        return
    exchange_rate = float(parts[1])
    bot.send_message(message.chat.id, "汇率已设置为 {:.2f}。".format(exchange_rate))


@bot.message_handler(func=lambda message: re.match("^(\+|-)\d+(\.\d+)?$", message.text) or "入款" in message.text or "下发" in message.text)
def handle_transaction(message):
    # 检查用户是否有权限
    if message.from_user.id not in authorized_users:
        return
    

    global global_rate
    group_id = message.chat.id  # 获取群组 ID
    create_global_account(group_id)  # 创建全局账户

    # 获取交易金额和类型
    if "入款" in message.text or "下发" in message.text:
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return

        transaction_type, amount_str = parts
        amount = float(amount_str)
        if transaction_type == "下发":
            amount = -amount
    else:
        amount = float(message.text)

    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()

    # 更新全局账户余额
    c.execute('UPDATE accounts SET balance = balance + ? WHERE user_id = -1 AND group_id = ?', (amount, group_id))

    # 记录交易
    c.execute('INSERT INTO transactions VALUES (?, ?, ?, ?)', (group_id, -1, datetime.now().strftime("%H:%M:%S"), amount))

    # 获取新的全局账户余额
    c.execute('SELECT balance FROM accounts WHERE user_id = -1 AND group_id = ?', (group_id,))
    new_balance = c.fetchone()[0]

    conn.commit()

    # 生成并发送交易报告
    c.execute('SELECT * FROM transactions WHERE user_id = -1 AND group_id = ? AND amount > 0', (group_id,))
    deposits = c.fetchall()
    c.execute('SELECT * FROM transactions WHERE user_id = -1 AND group_id = ? AND amount < 0', (group_id,))
    withdraws = c.fetchall()

    report = "入款（{}笔）\n".format(len(deposits))
    for t in deposits:
        amount = float(t[3])
        usdt = amount / exchange_rate
        report += "`{}`      {:.1f}     ({:.1f}U)\n".format(t[2], amount, usdt)  # 使用反引号包围时间
    report += "\n下发（{}笔）\n".format(len(withdraws))
    for t in withdraws:
        amount = -float(t[3])
        usdt = amount / exchange_rate
        report += "`{}`      {:.1f}     ({:.1f}U)\n".format(t[2], amount, usdt)  # 使用反引号包围时间

    total_deposit = sum(float(t[3]) for t in deposits)
    total_withdraw = sum(-float(t[3]) for t in withdraws)
    unissued = total_deposit - total_withdraw

    report += "\n汇率：{:.2f}\n费率：{:.2%}\n总入款：{:.1f} ({:.1f}U)\n总下发：{:.1f} ({:.1f}U)\n未下发：{:.1f} ({:.1f}U)".format(
        exchange_rate, global_rate, total_deposit, total_deposit / exchange_rate, total_withdraw, total_withdraw / exchange_rate, unissued, unissued / exchange_rate
    )

    # 创建一个按钮
    keyboard = types.InlineKeyboardMarkup(row_width=2)  # 设置每行的按钮数量为2
    button1 = types.InlineKeyboardButton(text="福利来供需", url="https://t.me/FLLG8")
    button2 = types.InlineKeyboardButton(text="福利来担保", url="https://t.me/fllww")
    button3 = types.InlineKeyboardButton(text="福利来公群", url="https://t.me/FLLG1")
    button4 = types.InlineKeyboardButton(text="福利来导航", url="https://t.me/FLLDH")
    keyboard.add(button1, button2)
    keyboard.add(button3, button4)

    bot.send_message(message.chat.id, report, parse_mode='Markdown', reply_markup=keyboard)

    conn.close()


@bot.message_handler(func=lambda message: message.text == "查看账单" and message.from_user.id in authorized_users)
def view_bill(message):
    group_id = message.chat.id  # 获取群组 ID
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()

    # 生成并发送交易报告
    c.execute('SELECT * FROM transactions WHERE user_id = -1 AND group_id = ? AND amount > 0', (group_id,))
    deposits = c.fetchall()
    c.execute('SELECT * FROM transactions WHERE user_id = -1 AND group_id = ? AND amount < 0', (group_id,))
    withdraws = c.fetchall()

    report = "入款（{}笔）\n".format(len(deposits))
    for t in deposits:
        amount = float(t[3])
        usdt = amount / exchange_rate
        report += "`{}`      {:.1f}     ({:.1f}U)\n".format(t[2], amount, usdt)  # 使用反引号包围时间
    report += "\n下发（{}笔）\n".format(len(withdraws))
    for t in withdraws:
        amount = -float(t[3])
        usdt = amount / exchange_rate
        report += "`{}`      {:.1f}     ({:.1f}U)\n".format(t[2], amount, usdt)  # 使用反引号包围时间

    total_deposit = sum(float(t[3]) for t in deposits)
    total_withdraw = sum(-float(t[3]) for t in withdraws)
    unissued = total_deposit - total_withdraw

    report += "\n汇率：{:.2f}\n费率：{:.2%}\n总入款：{:.1f} ({:.1f}U)\n总下发：{:.1f} ({:.1f}U)\n未下发：{:.1f} ({:.1f}U)".format(
        exchange_rate, global_rate, total_deposit, total_deposit / exchange_rate, total_withdraw, total_withdraw / exchange_rate, unissued, unissued / exchange_rate
    )

    bot.send_message(message.chat.id, report, parse_mode='Markdown')

    conn.close()


    
# 创建一个函数来清空记账记录
def clear_accounts():
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    c.execute('DELETE FROM accounts')
    c.execute('DELETE FROM transactions')
    conn.commit()
    conn.close()

# 设置定时任务，每1天执行一次
schedule.every(1).days.do(clear_accounts)

@bot.message_handler(func=lambda message: message.text == "设置操作人" and message.reply_to_message is not None)
def authorize_user(message):
    if message.from_user.id != ADMIN_ID:  # 检查发送消息的用户是否是管理员
        bot.send_message(message.chat.id, "对不起，只有管理员可以执行此操作。")
        return

    user_id = message.reply_to_message.from_user.id  # 获取被回复消息的发送者的用户 ID
    authorized_users.add(user_id)
    bot.send_message(ADMIN_ID, "用户 {} 已被授权记账权限。".format(user_id))
    bot.send_message(user_id, "你已被授权记账权限。")

@bot.message_handler(func=lambda message: message.text == "取消操作人" and message.reply_to_message is not None)
def deauthorize_user(message):
    if message.from_user.id != ADMIN_ID:  # 检查发送消息的用户是否是管理员
        bot.send_message(message.chat.id, "对不起，只有管理员可以执行此操作。")
        return

    user_id = message.reply_to_message.from_user.id  # 获取被回复消息的发送者的用户 ID
    if user_id in authorized_users:
        authorized_users.remove(user_id)
        bot.send_message(ADMIN_ID, "用户 {} 的记账权限已被取消。".format(user_id))
        bot.send_message(user_id, "你的记账权限已被取消。")
    else:
        bot.send_message(ADMIN_ID, "用户 {} 没有记账权限。".format(user_id))


@bot.message_handler(func=lambda message: message.text == "重置记账" and message.from_user.id in authorized_users)
def reset_accounts(message):
    conn = sqlite3.connect('accounts.db')
    c = conn.cursor()
    group_id = message.chat.id  # 获取群组 ID
    # 删除当前群组的所有交易和账户记录
    c.execute('DELETE FROM transactions WHERE group_id = ?', (group_id,))
    c.execute('DELETE FROM accounts WHERE group_id = ?', (group_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "当前群组的所有记账记录已被重置。")   


@bot.message_handler(func=lambda message: any(op in message.text for op in ['+', '-', '*', '/']))
def calculate(message):
    try:
        # Remove the equals sign if present
        expression = message.text.replace("=", "")
        result = eval(expression)
        bot.send_message(message.chat.id, str(result))
    except Exception as e:
        bot.send_message(message.chat.id, "无法计算表达式。")
        

import requests
from datetime import datetime
from pytz import timezone

@bot.message_handler(func=lambda message: re.match("^T[a-zA-Z0-9]{33}$", message.text))
def check_balance(message):
    address = message.text
    response = requests.get(f"https://api.trongrid.io/v1/accounts/{address}")
    data = response.json()
    balance = 0
    usdt_balance = 0

    if 'balance' in data['data'][0]:
        balance = int(data['data'][0]['balance']) / 10**6  # TRX has 6 decimal places

    for asset in data['data'][0].get('trc20', []):
        if 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t' in asset:  # replace with the contract address of your USDT
            usdt_balance = int(asset['TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t']) / 10**6  # USDT also has 6 decimal places

    # Get current time in Beijing
    beijing_time = datetime.now(timezone('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")

    bot.send_message(message.chat.id, f"查询地址：`{address}`\n\nTRX 余额: `{balance}`\nUSDT-TRC20 余额: `{usdt_balance}`\n\n当前北京时间: `{beijing_time}`", parse_mode='Markdown')


bot.infinity_polling()

# 在主循环中检查并执行定时任务
while True:
    schedule.run_pending()
    time.sleep(1)
