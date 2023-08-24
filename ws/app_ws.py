"""
FILE: app_ws.py

DESCRIPTION: Websocket server for AiFace device.

NOTES:
- Ensure that the AiFace device is connected to the same network as the server and points to the server's IP address.
- MySQL database should contain two tables for `reg` and `sendlog` commands (WIP).
- Redis database should contain two keys for `OUT` (sending to device) and `IN` (receiving from device).
"""

import asyncio
import websockets
import json
import datetime
from copy import deepcopy
import mysql.connector
import argparse
import redis
import os
import dotenv

def dtnow():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            print(f"[{dtnow()}] [{CLIENT_LOG_PREFIX}] Record from {message['sn']}: {show_dict(message['record'][i], ['enrollid', 'aliasid', 'name', 'time', 'mode', 'inout', 'event'])}.")

    return result

async def send_response(websocket, message):
    if message is not None:
        if "ret" in message.keys():
            if message['ret'] == 'reg':
                print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Register success on {message['cloudtime']}.")
            elif message['ret'] == 'sendlog':
                pass
        await websocket.send(json.dumps(message))
    else:
        raise Exception("Undefined message received.")

async def connect_mysql(sql_host, sql_user, sql_pass, sql_db):
    try:
        db = mysql.connector.connect(
            host=sql_host,
            user=sql_user,
            password=sql_pass,
            database=sql_db
        )

        return db
    except Exception as e:
        print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Error: Could not connect to MySQL database. {e}.")
        return None

async def insert_record(message, db, sql_table):
    if message['cmd'] == 'sendlog':
        cursor = db.cursor()
        sql = f"INSERT INTO {sql_table} (cmd, sn, enrollid, aliasid, name, time, mode, input, event) VALUES (%s, %s, %s)"
        val = [
            (
                message['record']['cmd'],
                message['record']['sn'],
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

def save_file(message, path):
    filename = None
    if "cmd" in message.keys():
        filename = message['cmd']
    elif "ret" in message.keys():
        filename = message['ret']

    if not os.path.exists(path):
        os.makedirs(path)
    if filename is not None:
        with open(os.path.join(path, filename + '.json'), 'w') as f:
            json.dump(message, f, indent=4)

# this function is called for each client connecting (after 'reg' handshake)
# this function will not be called if the client does not connect
async def handle(websocket, path, r_ip, r_port, sql_host, sql_user, sql_pass, sql_db, sql_table, insert=False, receive=False):
    # connect to databases
    device_sn = None
    if insert:
        sql_db = await connect_mysql(sql_host, sql_user, sql_pass, sql_db)
    if receive:
        r_db = redis.Redis(host=r_ip, port=r_port, db=0)

    while True:
        try:
            # read message from client
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=NEW_MESSAGE_TIMEOUT)
            except asyncio.TimeoutError:
                message = None

            if message is not None:
                message = json.loads(message)
                if device_sn is None and "sn" in message.keys():
                    device_sn = message['sn']
                save_file(message, RESPONSES_PATH)

                # get response
                if "cmd" in message.keys():
                    response = get_response(message)
                    if insert and sql_db is not None:
                        await insert_record(message, sql_db, sql_table)
                    await send_response(websocket, response)
                elif "ret" in message.keys():
                    if receive and device_sn is not None:
                        r_db.rpush(f"{REDIS_DB_PREFIX}_{device_sn}_{REDIS_INCOMING_KEY}", json.dumps(message))
                        print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Incoming message ({message['ret']}) received from {device_sn}.")

            # send message to client
            if device_sn is not None:
                if receive:
                    outgoing = r_db.lpop(f"{REDIS_DB_PREFIX}_{device_sn}_{REDIS_OUTGOING_KEY}")
                    if outgoing is not None:
                        outgoing = json.loads(outgoing.decode())
                        await send_response(websocket, outgoing)
                        print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Outgoing message sent to {device_sn}.")
                        if outgoing['cmd'] == 'reboot':
                            print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Rebooting {device_sn}. Bye bye!")
                            break
        except Exception as e:
            print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Error: {e}.")
            break
        finally:
            pass

async def main(ws_ip, ws_port, r_ip, r_port, sql_host, sql_user, sql_pass, sql_db, sql_table, insert, receive):
    async with websockets.serve(lambda websocket, path: handle(
        websocket, path, r_ip, r_port, sql_host, sql_user, sql_pass, sql_db, sql_table, insert, receive
    ), ws_ip, ws_port, ping_timeout=None, ping_interval=None):
        await asyncio.Future()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Websocket server for AiFace device.')
    parser.add_argument("--env", type=str, default="../.env", help="Config stored in an environment file.")
    parser.add_argument("--insert", action="store_true", help="Insert data to MySQL database.")
    parser.add_argument("--receive", action="store_true", help="Receive data from Redis database.")
    parser.set_defaults(insert=False, receive=False)
    args = parser.parse_args()

    opts = dotenv.dotenv_values(args.env)
    
    SERVER_LOG_PREFIX = opts["LOG_SERVER_PREFIX"]
    CLIENT_LOG_PREFIX = opts["LOG_CLIENT_PREFIX"]
    REDIS_DB_PREFIX = opts["REDIS_DB_PREFIX"]
    REDIS_OUTGOING_KEY = opts["REDIS_OUT_KEY"]
    REDIS_INCOMING_KEY = opts["REDIS_IN_KEY"]
    RESPONSES_PATH = opts["PATH_WS_RESPONSES"]
    NEW_MESSAGE_TIMEOUT = int(opts["TIMEOUT_WS_NEW_MESSAGE"])

    asyncio.run(main(
        opts["WEBSOCKET_IP"],
        int(opts["WEBSOCKET_PORT"]),
        opts["REDIS_IP"],
        int(opts["REDIS_PORT"]),
        opts["MYSQL_HOST"],
        opts["MYSQL_USER"],
        opts["MYSQL_PASS"],
        opts["MYSQL_DATA"],
        opts["MYSQL_TABL"],
        args.insert,
        args.receive
    ))