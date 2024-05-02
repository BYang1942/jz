import re
import sqlite3
import telebot
from telebot import types

from config import TOKEN  # 导入TOKEN

bot = telebot.TeleBot(TOKEN)

# 创建数据库连接和表
conn = sqlite3.connect('groups.db')
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY,
        admin_id TEXT NOT NULL,
        transaction_party TEXT NOT NULL,
        transaction_amount TEXT NOT NULL,
        order_completion_time TEXT NOT NULL,
        transaction_content TEXT NOT NULL
    )
''')
conn.commit()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=2)
    btn1 = types.KeyboardButton('我的报备')
    btn2 = types.KeyboardButton('我的订单')
    keyboard.add(btn1, btn2)
    bot.send_message(message.chat.id, "欢迎使用", reply_markup=keyboard)

import threading

# 创建线程局部对象
tls = threading.local()

def get_db():
    # 检查当前线程是否已经有数据库连接
    db = getattr(tls, 'db', None)
    if db is None:
        # 如果没有，创建一个新的连接并存储在线程局部对象上
        db = tls.db = sqlite3.connect('groups.db')
    return db


# 创建 groups 表
c.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY,
        group_id TEXT NOT NULL,
        group_number INTEGER
    )
''')
conn.commit()

# 创建管理员表
c.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY,
        group_id TEXT NOT NULL,
        admin_id TEXT NOT NULL,
        has_template INTEGER DEFAULT 0
    )
''')
conn.commit()

@bot.message_handler(regexp=r'^/(\d+)$')
def handle_group_number(message):
    # 获取当前线程的数据库连接
    db = get_db()
    c = db.cursor()

    # 检查发送者是否是任何群组的管理员
    c.execute('SELECT * FROM admins WHERE admin_id = ?', (message.from_user.id,))
    admin = c.fetchone()

    if admin is None:  # 如果不是管理员，尝试从 Telegram API 中获取管理员信息
        admins = bot.get_chat_administrators(message.chat.id)
        for admin in admins:
            if admin.user.id == message.from_user.id:
                break
        else:  # 如果发送者不是管理员，直接返回，不处理消息
            return


    group_number = int(re.match(r'^/(\d+)$', message.text).group(1))
    group_id = message.chat.id

    # 检查该群组是否已经有编号
    c.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
    group = c.fetchone()

    if group is None:
        # 如果没有编号，插入新的编号
        c.execute('INSERT INTO groups (group_id, group_number) VALUES (?, ?)', (group_id, group_number))
    else:
        # 如果已经有编号，更新这个编号
        c.execute('UPDATE groups SET group_number = ? WHERE group_id = ?', (group_number, group_id))

    # 删除该群组的所有旧的管理员信息
    c.execute('DELETE FROM admins WHERE group_id = ?', (group_id,))

    # 获取并存储新的管理员信息
    admins = bot.get_chat_administrators(group_id)
    for admin in admins:
        c.execute('INSERT INTO admins (group_id, admin_id) VALUES (?, ?)', (group_id, admin.user.id))

    db.commit()
    print(f"Set group number {group_number} for group {group_id} into the database.")  # 添加的日志语句
    print(f"Updated admins for group {group_id} into the database.")  # 添加的日志语句

    bot.reply_to(message, f"群编号已设置为 {group_number}")

@bot.message_handler(commands=['报备'])
def handle_report(message):
    # 获取当前线程的数据库连接
    db = get_db()
    c = db.cursor()

    # 检查发送者是否是任何群组的管理员
    c.execute('SELECT * FROM admins WHERE admin_id = ?', (message.from_user.id,))
    admin = c.fetchone()

    if admin is not None:
        # 如果是管理员，发送报备模板
        bot.reply_to(message, '''
*以下为报备模板请务必按要求填写*
*交易方：*
*交易金额：*
*订单完成时间：*
*交易内容：*
        ''', parse_mode='Markdown')

        # 更新 has_template 字段
        c.execute('UPDATE admins SET has_template = 1 WHERE admin_id = ?', (message.from_user.id,))
        db.commit()
    else:
        # 如果不是管理员，发送错误消息
        bot.reply_to(message, '你不是任何群组的管理员，无法进行报备。')




@bot.message_handler(func=lambda message: message.text == '我的报备')
def handle_my_reports(message):
    # 获取当前线程的数据库连接
    db = get_db()
    c = db.cursor()

    # 检查发送者是否是任何群组的管理员
    c.execute('SELECT * FROM admins WHERE admin_id = ?', (message.from_user.id,))
    admin = c.fetchone()

    if admin is not None:
        # 如果是管理员，查询他的报备信息
        c.execute('SELECT * FROM reports WHERE admin_id = ?', (message.from_user.id,))
        reports = c.fetchall()

        if len(reports) == 0:
            # 如果没有报备信息，发送错误消息
            bot.reply_to(message, '你所在的群组还没有报备信息。')
        else:
            # 将报备信息格式化为字符串
            reports_str = '\n'.join([f"交易方：{report[2]}\n交易金额：{report[3]}\n订单完成时间：{report[4]}\n交易内容：{report[5]}" for report in reports])

            # 发送报备信息给管理员
            bot.reply_to(message, reports_str)
    else:
        # 如果不是管理员，发送错误消息
        bot.reply_to(message, '你不是任何群组的管理员，无法查看报备信息。')


@bot.message_handler(func=lambda message: message.text == '我的订单')
def handle_my_orders(message):
    # 获取当前线程的数据库连接
    db = get_db()
    c = db.cursor()


    # 打印查询的用户名
    print(f"Querying for username: {message.from_user.username}")

    # 检查发送者是否是任何群组的交易方
    c.execute('SELECT * FROM reports WHERE transaction_party = ?', ('@' + message.from_user.username,))
    reports = c.fetchall()

    # 打印查询结果
    print(f"Query results: {reports}")

    if len(reports) == 0:
        # 如果没有报备信息，发送错误消息
        bot.reply_to(message, '你所在的群组还没有报备信息。')
    else:
        # 将报备信息格式化为字符串
        reports_str = '\n'.join([f"交易方：{report[2]}\n交易金额：{report[3]}\n订单完成时间：{report[4]}\n交易内容：{report[5]}" for report in reports])

        # 发送报备信息给客户
        bot.reply_to(message, reports_str)


@bot.message_handler(func=lambda message: re.match(r'交易方：(.+)\n交易金额：(.+)\n订单完成时间：(.+)\n交易内容：(.+)', message.text))
def handle_report_submission(message):
    # 获取当前线程的数据库连接
    db = get_db()
    c = db.cursor()

    # 检查发送者是否是任何群组的管理员
    c.execute('SELECT * FROM admins WHERE admin_id = ?', (message.from_user.id,))
    admin = c.fetchone()

    if admin is not None and admin[3] != 0:  # 如果是管理员，并且他已经获取了报备模板
        # 检查报备的格式
        report_pattern = r'交易方：(.+)\n交易金额：(.+)\n订单完成时间：(.+)\n交易内容：(.+)'
        match = re.match(report_pattern, message.text)
        if match is not None:  # 如果报备的格式符合
            # 查询管理员管理的所有群组编号
            c.execute('SELECT group_number FROM groups WHERE group_id IN (SELECT group_id FROM admins WHERE admin_id = ?)', (message.from_user.id,))
            groups = c.fetchall()

            if len(groups) == 1:
                # 如果管理员只管理一个群组，直接发送报备信息
                send_report_to_group(db, c, message, match, groups[0][0])
            elif len(groups) > 1:
                # 如果管理员管理多个群组，询问他们想要发送到哪个群组编号
                markup = types.InlineKeyboardMarkup()
                for group in groups:
                    group_number = group[0]
                    callback_data = f"report:{group_number}:{match.group(1)}:{match.group(2)}:{match.group(3)}:{match.group(4)}"
                    markup.add(types.InlineKeyboardButton(f"群组编号 {group_number}", callback_data=callback_data))
                bot.send_message(message.chat.id, "请选择要发送报备信息的群组编号：", reply_markup=markup)
            else:
                # 如果管理员没有管理的群组
                bot.reply_to(message, "你没有管理的群组。")
        else:
            # 如果报备的格式不符合
            bot.reply_to(message, "报备信息格式不正确，请按照模板填写。")
    else:
        # 如果不是管理员或者没有获取报备模板
        bot.reply_to(message, "你不是管理员，或者你还没有获取报备模板。")

def send_report_to_group(db, c, message, transaction_party, transaction_amount, order_completion_time, transaction_content, group_number):
    # 根据群组编号找到群组ID
    c.execute('SELECT group_id FROM groups WHERE group_number = ?', (group_number,))
    group = c.fetchone()
    if group:
        group_id = group[0]
        # 修改报备信息，隐藏交易方
        modified_message = f'*交易方：* [隐藏]\n*交易金额：* {transaction_amount}\n*订单完成时间：* {order_completion_time}\n*交易内容：* {transaction_content}'
        # 发送修改后的报备信息到指定群组
        bot.send_message(group_id, modified_message, parse_mode='Markdown')

        # 创建按钮
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton("按钮1", callback_data='btn1')
        btn2 = types.InlineKeyboardButton("按钮2", callback_data='btn2')
        btn3 = types.InlineKeyboardButton("按钮3", callback_data='btn3')
        btn4 = types.InlineKeyboardButton("按钮4", callback_data='btn4')
        markup.add(btn1, btn2, btn3, btn4)

        # 发送报备成功消息和按钮到群组
        bot.send_message(group_id, "报备成功，客户已确认", reply_markup=markup)

        # 回复发送者报备信息已发送
        bot.reply_to(message, f"报备信息已发送到群组编号 {group_number}。")
    else:
        bot.reply_to(message, f"找不到群组编号 {group_number} 对应的群组。")

@bot.callback_query_handler(func=lambda call: call.data.startswith('report:'))
def handle_report_callback_query(call):
    # 解析回调数据
    _, group_number, transaction_party, transaction_amount, order_completion_time, transaction_content = call.data.split(':', 5)
    group_number = int(group_number)

    # 获取当前线程的数据库连接
    db = get_db()
    c = db.cursor()

    # 发送报备信息到指定群组
    send_report_to_group(db, c, call.message, transaction_party, transaction_amount, order_completion_time, transaction_content, group_number)

    # 确认回调请求已被处理
    bot.answer_callback_query(call.id)

    # 存储报备信息到数据库
    c.execute('INSERT INTO reports (admin_id, transaction_party, transaction_amount, order_completion_time, transaction_content) VALUES (?, ?, ?, ?, ?)', 
              (call.from_user.id, transaction_party, transaction_amount, order_completion_time, transaction_content))
    db.commit()

    # 打印数据库操作的结果
    print(f"Inserted report into the database: {c.lastrowid}")

bot.infinity_polling()