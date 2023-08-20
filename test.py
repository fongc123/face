import asyncio
import websockets
import json
import datetime
from copy import deepcopy
# import mysql
import argparse

def dtnow():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

SERVER_LOG_PREFIX = "SERVER"
CLIENT_LOG_PREFIX = "CLIENT"
REGISTER_SUCCESS_RESPONSE = {
    "ret" : "reg",
    "result" : True,
    "cloudtime" : dtnow(),
    "nosenduser" : True
}

SENDLOG_SUCCESS_RESPONSE = {
    "ret" : "sendlog",
    "result" : True,
    "count" : 999,
    "logindex" : 999,
    "cloudtime" : dtnow(),
    "access" : 1
}

SENDLOG_FAIL_RESPONSE = {
    "ret" : "sendlog",
    "result" : False,
    "reason" : "1"
}

def show_dict(d, keys):
    return ', '.join(f'{k}={d[k]}' for k in keys)

def get_response(message):
    result = None
    if message['cmd'] == 'reg':
        result = deepcopy(REGISTER_SUCCESS_RESPONSE)
        result['cloudtime'] = dtnow()

        print(f"[{dtnow()}] [{CLIENT_LOG_PREFIX}] Register request received by {message['sn']}. Device info: {show_dict(message['devinfo'], ['modelname', 'netinuse', 'fpalgo', 'firmware', 'time', 'mac'])}.")
    elif message['cmd'] == 'sendlog':
        result = deepcopy(SENDLOG_SUCCESS_RESPONSE)
        result['cloudtime'] = dtnow()
        result['count'] = message['count']
        result['logindex'] = message['logindex']

        for i in range(message['count']):
            print(f"[{dtnow()}] [{CLIENT_LOG_PREFIX}] Record from {message['sn']}: {show_dict(message['record'][i], ['enrollid', 'aliasid', 'name', 'time', 'mode', 'inout', 'event'])}")

    return result

async def send_response(websocket, message):
    if message is not None:
        if message['ret'] == 'reg':
            print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Register success on {message['cloudtime']}.")
        elif message['ret'] == 'sendlog':
            pass
        await websocket.send(json.dumps(message))
    else:
        raise Exception("Undefined message received.")
    
async def insert_db(message, sql_host, sql_user, sql_pass, sql_db, sql_table):
    if message['cmd'] == 'sendlog':
        try:
            db = mysql.connector.connect(
                host=sql_host,
                user=sql_user,
                password=sql_pass,
                database=sql_db
            )

            cursor = db.cursor()
            sql = f"INSERT INTO {sql_table} (column1, column2, column3) VALUES (%s, %s, %s)"
            val = [
                (
                    message['record'][i]['enrollid'],
                    message['record'][i]['aliasid'],
                    message['record'][i]['name'],
                    message['record'][i]['time'],
                    message['record'][i]['mode'],
                    message['record'][i]['inout'],
                    message['record'][i]['event']
                ) for i in range(message['count'])
            ]
            cursor.execute(sql, val)
            db.commit()
        except Exception as e:
            print(f"Error: {e}")
        finally:
            db.close()

def save_file(message):
    if message['cmd'] == 'reg':
        with open('reg.json', 'w') as f:
            json.dump(message, f, indent=4)
    elif message['cmd'] == 'sendlog':
        with open('sendlog.json', 'w') as f:
            json.dump(message, f, indent=4)

async def handle(websocket, path, sql_host, sql_user, sql_pass, sql_db, sql_table):
    print('hi')
    while True:
        try:
            # read message from client
            message = await websocket.recv()
            message = json.loads(message)
            save_file(message)

            # get response
            response = get_response(message)
            # insert_db(message, sql_host, sql_user, sql_pass, sql_db, sql_table)
            await send_response(websocket, response)
        except Exception as e:
            print(f"Error: {e}")
            break
        finally:
            pass

async def main(listen_ip, listen_port, sql_host, sql_user, sql_pass, sql_db, sql_table):
    async with websockets.serve(lambda websocket, path: handle(websocket, path, sql_host, sql_user, sql_pass, sql_db, sql_table), listen_ip, listen_port, ping_timeout=None, ping_interval=None):
        await asyncio.Future()

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description='Websocket server for AiFace device.')
    # parser.add_argument('-i', '--listen_ip', type=str, default='localhost', help='IP address to listen on.')
    # parser.add_argument('-p', '--listen_port', type=int, default=7788, help='Port to listen on.')
    # parser.add_argument('-host', '--sql_host', type=str, default='localhost', help='MySQL host.')
    # parser.add_argument('-u', '--sql_user', type=str, default='root', help='MySQL user.')
    # parser.add_argument('-pw', '--sql_pass', type=str, default='password', help='MySQL password.')
    # parser.add_argument('-db', '--sql_db', type=str, default='database', help='MySQL database.')
    # parser.add_argument('-t', '--sql_table', type=str, default='records', help='MySQL table.')
    # args = parser.parse_args()

    # asyncio.run(main(args.listen_ip, args.listen_port, args.sql_host, args.sql_user, args.sql_pass, args.sql_db, args.sql_table))
    asyncio.run(main("169.254.121.173", 7788, "k", "k", "k", "k", "k"))