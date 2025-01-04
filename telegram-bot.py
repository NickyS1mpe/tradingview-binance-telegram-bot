import json
import logging
import os
import random
import sys
import time

import requests
from config import keys
from chartsUtils import take_tradingview_screenshot
from binance.lib.utils import config_logging
from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient

# Bot token from Telegram BotFather
bot_token = keys['bot_token']
api = f'https://api.telegram.org/bot{bot_token}/'

# Bot statement
bot_statement = keys['statement']
# Bot nickname
bot_nickname = r'[TestBot]{1}'
# Bot username
bot_username = '@username'
group_user_nickname = ""
# Allowed group and the enable status of the group
group = {
    keys['default_group']: True
}
block_user = []
factor = {}
alert = {}
clients = {}
client_id = 1
um_futures_client = ""
# log
log_file = 'data/bot.log'
logging.basicConfig(filename=log_file,
                    level=logging.INFO)


# Logging
def log_message(update):
    user_name = update['message']['from_user']['user_name']
    chat_name = update['chat']['chat_name']
    is_bot = update['message']['from_user']['is_bot']
    message_type = update['message']['message_type']
    message_content = update['message']['text']

    logging.info(
        '%(asctime)s - %(user_name)s - %(chat_name)s - %(is_bot)s - %(message_type)s - %(message_content)s',
        {'asctime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), 'user_name': user_name,
         'chat_name': chat_name, 'is_bot': is_bot,
         'message_type': message_type,
         'message_content': message_content})


# Fetch the information of bot
def getMe():
    return json.loads(requests.get(api + 'getMe').content)


# Reply to message via bot
def telegram_bot_sendText(bot_msg, chat_id, msg_id):
    data = {
        'chat_id': chat_id,
        'text': bot_msg,
        'reply_to_message_id': msg_id
    }
    url = api + 'sendMessage'

    response = requests.post(url, data=data)
    return response.json()


# Send text via bot
def telegram_bot_send(bot_msg, chat_id):
    data = {
        'chat_id': chat_id,
        'text': bot_msg,
    }
    url = api + 'sendMessage'

    response = requests.post(url, data=data)
    return response.json()


# Send photo via bot
def telegram_bot_sendImage(image_url, chat_id, msg_id):
    url = api + 'sendPhoto'
    data = {
        'chat_id': chat_id,
        'reply_to_message_id': msg_id
    }
    with open(image_url, "rb") as photo:
        files = {
            "photo": photo
        }
        response = requests.post(url, data=data, files=files)
    if os.path.exists(image_url):
        os.remove(image_url)
    return response.json()


# Fetch photo via bot
def telegram_bot_getImage(file_id, update_id):
    # Fetch the location of the photo in Telegram server
    location = api + 'getFile?file_id=' + file_id
    response = requests.get(location)
    response_dict = response.json()
    file_path = response_dict['result']['file_path']
    # Download the image
    image_url = 'https://api.telegram.org/file/bot' + bot_token + '/' + file_path
    response = requests.get(image_url)
    if response.status_code == 200:
        with open(f'image/{update_id}.jpg', 'wb') as f:
            f.write(response.content)
    return image_url


def coin_price_listener(_, message):
    message_dict = json.loads(message)
    print(message_dict)
    if 's' in message_dict and message_dict['s'] in alert:
        name = message_dict['s']
        price = int(float(message_dict['p']))
        if (price - price % factor[name]) / factor[name] != (
                alert[name] - alert[name] % factor[name]) / factor[name]:
            if price > alert[name]:
                print(telegram_bot_send(
                    "Binance-" + name + " is upward $" + str(
                        price - price % factor[name]),
                    -4184327943))
            else:
                print(telegram_bot_send(
                    "Binance-" + name + " is below $" + str(
                        alert[name] - alert[name] % factor[name]),
                    -4184327943))

        alert[name] = price


def agg_trade_handler(_, message):
    message_dict = json.loads(message)
    print(message_dict)
    if 's' in message_dict and float(message_dict['q']) >= 20:
        if bool(message_dict['m']):
            print(telegram_bot_send(
                "Position: SELL" + "\nPrice: " + message_dict['p'] + "\nQuantity: " + message_dict['q'],
                -4184327943))
        else:
            print(telegram_bot_send(
                "Position: BUY" + "\nPrice: " + message_dict['p'] + "\nQuantity: " + message_dict['q'],
                -4184327943))


def task():
    # Fetch the current document location
    cwd = os.getcwd()
    # Get the timestamp in timer_log.txt or create a new one if it isn't existed
    timer_log = cwd + '/timer_log.txt'
    if not os.path.exists(timer_log):
        with open(timer_log, "w") as f:
            f.write('1')
    # else:
    # print("Timer Log Exists")

    with open(timer_log) as f:
        last_update = f.read()

    # Set offset based on timestamp to fetch the latest messages
    url = f'{api}getUpdates?offset={last_update}'
    response = requests.get(url)
    data = json.loads(response.content)
    global bot_enable
    global client_id
    global um_futures_client

    # Read the data
    for res in data['result']:
        try:
            if 'message' in res:
                comment = ''
                update_id = res['update_id']
                chat_id = res['message']['chat']['id']
                msg_id = res['message']['message_id']
                # If data type is photo
                if 'text' in res['message']:
                    comment = res['message']['text']

                # Renew the timestamp
                with open(timer_log, "w") as f:
                    f.write(f'{update_id}')

                if float(update_id) > float(last_update) and comment != "":
                    if not res['message']['from']['is_bot']:
                        group_name = res['message']['chat']['title'] if 'title' in res['message']['chat'] else \
                            res['message']['chat']['type']
                        group_id = res['message']['chat']['id']
                        user_name = res['message']['from']['first_name']
                        message_type = res['message']['chat']['type']

                        # Check is the bot is allowed to use in the group, and the bot is enabled
                        if group_id in group:
                            # Set the log contents
                            update = {'message': {'from_user': {'user_name': user_name, 'is_bot': 'False'},
                                                  'message_type': message_type,
                                                  'text': comment.replace("\n", "").replace("\t", "")},
                                      'chat': {'chat_name': group_name}}
                            if group[group_id]:

                                # Disable the bot in a group
                                if '/disable_bot' in comment:
                                    group[group_name] = False
                                    update['message']['message_type'] = 'command disable the bot'
                                    log_message(update)
                                    print(telegram_bot_send('Bot disabled', chat_id))

                                # Return the introduction of the bot
                                elif '/info' in comment:
                                    bot_info = getMe()
                                    bot_response = "I'm a Telegram auto reply BOT - " + f"{bot_info['result']['first_name']}"
                                    update['message']['message_type'] = 'command get the bot info'
                                    log_message(update)
                                    print(telegram_bot_send(bot_response + "\n" + bot_statement, chat_id))

                                elif '/coin' in comment:
                                    coin_name = str.upper(comment.split(" ")[1])
                                    update['message']['message_type'] = 'command get coin price'
                                    if len(coin_name) == 0:
                                        print(telegram_bot_send("Example command: /coin btcusdt", chat_id))
                                    else:
                                        config_logging(logging, logging.DEBUG)
                                        coin_data = um_futures_client.mark_price(coin_name)
                                        print(telegram_bot_send(
                                            "Symbol: " + coin_data['symbol'] + "\nMark Price: " +
                                            str(round(float(coin_data['markPrice']), 2)) + "\nFunding Rate: " +
                                            str(round(float(coin_data['lastFundingRate']) * 100, 4)) + "%",
                                            chat_id))
                                    log_message(update)

                                elif '/alert' in comment:
                                    coin_name = str.upper(comment.split(" ")[1])
                                    fac = comment.split(" ")[2]
                                    update['message']['message_type'] = 'command add coin alert'
                                    if len(coin_name) == 0 or len(fac) == 0:
                                        print(telegram_bot_send("Example command: /alert btcusdt 1000", chat_id))
                                    else:
                                        if coin_name in alert:
                                            print(telegram_bot_send(
                                                "Coin " + coin_name + " has already added to price alert", chat_id))
                                        else:
                                            coin_data = um_futures_client.mark_price(coin_name)
                                            alert[coin_name] = int(float(coin_data['markPrice']))
                                            factor[coin_name] = int(fac)
                                            clients[coin_name] = UMFuturesWebsocketClient(
                                                on_message=coin_price_listener)
                                            clients[coin_name].mark_price(
                                                symbol=coin_name,
                                                id=client_id,
                                                speed=1,
                                            )
                                            client_id += 1
                                            print(telegram_bot_send("Coin " + coin_name + " has added to price alert",
                                                                    chat_id))
                                    log_message(update)

                                elif '/24hr' in comment:

                                    update['message']['message_type'] = 'command 24hr coin price change'
                                    if len(comment.split(" ")) < 2:
                                        print(telegram_bot_send("Example command: /24hr btcusdt", chat_id))
                                    else:
                                        coin_name = str.upper(comment.split(" ")[1])
                                        config_logging(logging, logging.DEBUG)
                                        coin_data = um_futures_client.ticker_24hr_price_change(coin_name)
                                        print(telegram_bot_send(
                                            "Symbol: " + coin_data['symbol'] + "\nPrice Change: " +
                                            coin_data['priceChange'] + "\nPrice Change Percent: " +
                                            coin_data['priceChangePercent'] + "%\nWeighted Avg Price: " +
                                            coin_data['weightedAvgPrice'] + "\nOpen Price: " +
                                            coin_data['openPrice'] + "\nHigh Price: " +
                                            coin_data['highPrice'] + '\nLow Price: ' +
                                            coin_data['lowPrice'],
                                            chat_id))
                                    log_message(update)

                                elif '/chart' in comment:
                                    coin_name = str.upper(comment.split(" ")[1])
                                    update['message']['message_type'] = 'command chart coin price'
                                    if len(coin_name) == 0:
                                        print(telegram_bot_send("Example command: /chart btcusdt 1h", chat_id))
                                    else:
                                        tradingview_url = keys['tradingview_url'] + coin_name
                                        if len(comment.split(" ")) > 2 and len(comment.split(" ")[2]) > 0:
                                            tradingview_url += "&interval=" + comment.split(" ")[2]
                                        img_url = "./image/" + str(msg_id) + ".png"
                                        take_tradingview_screenshot(tradingview_url, img_url)
                                        print(telegram_bot_sendImage(img_url, chat_id, msg_id))
                                    log_message(update)

                                elif "/aon" in comment:
                                    update['message']['message_type'] = 'command coin price alert on'
                                    for k in alert:
                                        clients[k] = UMFuturesWebsocketClient(on_message=coin_price_listener)
                                        clients[k].mark_price(
                                            symbol=k,
                                            id=client_id,
                                            speed=1,
                                        )
                                        client_id += 1
                                    print(telegram_bot_send("Coin price alert is enabled", chat_id))
                                    log_message(update)

                                elif "/aof" in comment:
                                    update['message']['message_type'] = 'command coin price alert off'
                                    for k in clients:
                                        clients[k].stop()
                                    print(telegram_bot_send("Coin price alert is disabled", chat_id))
                                    log_message(update)

                                elif "/ali" in comment:
                                    update['message']['message_type'] = 'command get coin price alert list'
                                    li = ""
                                    for k in alert:
                                        li += k + "\n"
                                    print(telegram_bot_send(li + "Send /alert to add a new price alert", chat_id))
                                    log_message(update)

                                elif "/remove" in comment:
                                    update['message']['message_type'] = 'command remove coin price alert'
                                    if len(comment.split(" ")) < 2:
                                        print(telegram_bot_send("Example command: /24hr btcusdt", chat_id))
                                    else:
                                        coin_name = str.upper(comment.split(" ")[1])
                                        if coin_name in alert:
                                            del alert[coin_name]
                                            del factor[coin_name]
                                            if coin_name in clients:
                                                clients[coin_name].stop()
                                                del clients[coin_name]

                                            print(telegram_bot_send("Alert for " + coin_name + " has stopped", chat_id))
                                        else:
                                            print(
                                                telegram_bot_send(coin_name + " has not been added to alert", chat_id))
                                    log_message(update)

                                elif "糯糯" in comment:
                                    print(telegram_bot_send("啊啊啊啊啊啊糯糯糯糯糯糯糯糯我要炒币养你",
                                                            chat_id))

                                elif "梭哈" in comment:
                                    slogan = [
                                        "打工十年还是工，梭哈一夜住皇宫", "爱拼才会赢", "赌场十分钟，少打十年工",
                                        "哪有小孩天天哭，哪有赌徒天天输", "搏一搏，单车变摩托；赌一赌，摩托变路虎。"
                                    ]
                                    ran = random.randint(0, len(slogan))
                                    print(telegram_bot_send(slogan[ran],
                                                            chat_id))

                            # Enable the bot in a group
                            if '/enable_bot' in comment:
                                group[group_name] = True
                                update['message']['message_type'] = 'command enable the bot'
                                log_message(update)
                                print(telegram_bot_send('Bot enabled', chat_id))

        except Exception as e:
            logging.error(e)


def loadData():
    global alert
    global factor
    with open("data/alert.txt", "r") as file:
        alert = json.load(file)

    with open("data/factor.txt", "r") as file:
        factor = json.load(file)


def saveData():
    global alert
    global factor
    with open("data/alert.txt", "w") as file:
        json.dump(alert, file)

    with open("data/factor.txt", "w") as file:
        json.dump(factor, file)


if __name__ == "__main__":
    # Loading cookies

    print(getMe())

    loadData()

    um_futures_client = UMFutures()

    # trade_client = UMFuturesWebsocketClient(on_message=agg_trade_handler, is_combined=True)
    # trade_client.agg_trade(symbol="BTCUSDT")

    try:
        while True:
            task()
            time.sleep(5)
    except BaseException as e:
        logging.error(e)
    finally:
        saveData()
        # trade_client.agg_trade(symbol="BTCUSDT", action=UMFuturesWebsocketClient.ACTION_UNSUBSCRIBE)
        # trade_client.stop()
        for key in clients:
            clients[key].stop()
        sys.exit()
