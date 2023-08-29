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
import pymssql
import argparse
import redis
import os

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

# class to store logs in text file
class LogRecord:
    def __init__(self, path):
        self.path = path
        self.file = None

    def open(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)
        self.file = open(os.path.join(self.path, 'log.txt'), 'a')

    def close(self):
        if self.file is not None:
            self.file.close()

    def write(self, message):
        if self.file is not None:
            self.file.write(f"{message}\n")

def show_dict(d, keys):
    return ', '.join(f'{k}={d[k]}' for k in keys)

def get_response(message):
    LOG_FILE.open()
    result = None
    if message['cmd'] == 'reg':
        result = deepcopy(REGISTER_SUCCESS_RESPONSE)
        result['cloudtime'] = dtnow()

        print(f"[{dtnow()}] [{CLIENT_LOG_PREFIX}] Register request received by {message['sn']}. Device info: {show_dict(message['devinfo'], ['modelname', 'netinuse', 'fpalgo', 'firmware', 'time', 'mac'])}.")
        LOG_FILE.write(f"[{dtnow()}] [{CLIENT_LOG_PREFIX}] Register request received by {message['sn']}. Device info: {show_dict(message['devinfo'], ['modelname', 'netinuse', 'fpalgo', 'firmware', 'time', 'mac'])}.")
    elif message['cmd'] == 'sendlog':
        result = deepcopy(SENDLOG_SUCCESS_RESPONSE)
        result['cloudtime'] = dtnow()
        result['count'] = message['count']
        result['logindex'] = message['logindex']

        for i in range(message['count']):
            print(f"[{dtnow()}] [{CLIENT_LOG_PREFIX}] Record from {message['sn']}: {show_dict(message['record'][i], ['enrollid', 'aliasid', 'name', 'time', 'mode', 'inout', 'event'])}.")
            LOG_FILE.write(f"[{dtnow()}] [{CLIENT_LOG_PREFIX}] Record from {message['sn']}: {show_dict(message['record'][i], ['enrollid', 'aliasid', 'name', 'time', 'mode', 'inout', 'event'])}.")

    LOG_FILE.close()
    return result

async def send_response(websocket, message):
    if message is not None:
        if "ret" in message.keys():
            if message['ret'] == 'reg':
                LOG_FILE.open()
                print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Register success on {message['cloudtime']}.")
                LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Register success on {message['cloudtime']}.")
                LOG_FILE.close()
            elif message['ret'] == 'sendlog':
                pass
        await websocket.send(json.dumps(message))
    else:
        raise Exception("Undefined message received.")

async def connect_mssql(sql_host, sql_user, sql_pass, sql_db):
    try:
        db = pymssql.connect(sql_host, sql_user, sql_pass, sql_db)

        return db
    except Exception as e:
        LOG_FILE.open()
        print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Error: Could not connect to MSSQL database. {e}.")
        LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Error: Could not connect to MSSQL database. {e}.")
        LOG_FILE.close()
        return None

async def insert_record(message, db, sql_table):
    if message['cmd'] == 'sendlog':
        cursor = db.cursor()

        # create table if not exist
        _script_create_table = f"""
        IF OBJECT_ID('{sql_table}', 'U') IS NULL
            CREATE TABLE {sql_table} (
                cmd VARCHAR(255),
                sn VARCHAR(255),
                enrollid INT,
                aliasid INT,
                name VARCHAR(255),
                time VARCHAR(255),
                mode INT,
                inout INT,
                event INT
            )
        """
        cursor.execute(_script_create_table)
        db.commit()

        sql = f"""
        INSERT INTO {sql_table} (cmd, sn, enrollid, aliasid, name, time, mode, inout, event) VALUES (%s, %s, %d, %d, %s, %s, %d, %d, %d)
        """
        val = [(
            message['cmd'],
            message['sn'],
            message['record'][i]['enrollid'],
            message['record'][i]['aliasid'],
            message['record'][i]['name'],
            message['record'][i]['time'],
            message['record'][i]['mode'],
            message['record'][i]['inout'],
            message['record'][i]['event']
        ) for i in range(message['count'])]
        cursor.executemany(sql, val)
        db.commit()

        LOG_FILE.open()
        print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Inserted {message['count']} records from {message['sn']} to {sql_table}.")
        LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Inserted {message['count']} records from {message['sn']} to {sql_table}.")
        LOG_FILE.close()

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
        sql_db = await connect_mssql(sql_host, sql_user, sql_pass, sql_db)
    if receive:
        r_db = redis.Redis(host=r_ip, port=r_port, db=0)

    no_message_counter = 0
    while True:
        LOG_FILE.open()
        try:
            # read message from client
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=NEW_MESSAGE_TIMEOUT)
                no_message_counter = 0
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
                        LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Incoming message ({message['ret']}) received from {device_sn}.")
            else:
                no_message_counter += 1
                if no_message_counter >= MAX_MESSAGE_TIMEOUT: # if no message received for a long time (default: ~ 5 min.), break
                    print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Idle timeout for device {device_sn} exceeded. Bye bye!")
                    LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Idle timeout for device {device_sn} exceeded.")
                    break

            # send message to client
            if device_sn is not None:
                if receive:
                    outgoing = r_db.lpop(f"{REDIS_DB_PREFIX}_{device_sn}_{REDIS_OUTGOING_KEY}")
                    if outgoing is not None:
                        outgoing = json.loads(outgoing.decode())
                        await send_response(websocket, outgoing)
                        print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Outgoing message sent to {device_sn}.")
                        LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Outgoing message sent to {device_sn}.")
                        if outgoing['cmd'] == 'reboot':
                            print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Rebooting {device_sn}. Bye bye!")
                            LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Rebooting {device_sn}.")
                            break
        except Exception as e:
            print(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Error: {e}.")
            LOG_FILE.write(f"[{dtnow()}] [{SERVER_LOG_PREFIX}] Error: {e}.")
            break
        finally:
            LOG_FILE.close()

async def main(ws_ip, ws_port, r_ip, r_port, sql_host, sql_user, sql_pass, sql_db, sql_table, insert, receive):
    async with websockets.serve(lambda websocket, path: handle(
        websocket, path, r_ip, r_port, sql_host, sql_user, sql_pass, sql_db, sql_table, insert, receive
    ), ws_ip, ws_port, ping_timeout=None, ping_interval=None):
        await asyncio.Future()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Websocket server for AiFace device.')
    parser.add_argument("--env", type=str, default="../.env", help="Config stored in an environment file.")
    parser.add_argument("--insert", action="store_true", help="Insert data to Microsoft SQL database.")
    parser.add_argument("--receive", action="store_true", help="Receive data from Redis database.")
    parser.set_defaults(insert=False, receive=False)
    args = parser.parse_args()
    
    SERVER_LOG_PREFIX = os.getenv("LOG_SERVER_PREFIX")
    CLIENT_LOG_PREFIX = os.getenv("LOG_CLIENT_PREFIX")
    REDIS_DB_PREFIX = os.getenv("REDIS_DB_PREFIX")
    REDIS_OUTGOING_KEY = os.getenv("REDIS_OUT_KEY")
    REDIS_INCOMING_KEY = os.getenv("REDIS_IN_KEY")
    RESPONSES_PATH = os.getenv("PATH_WS_RESPONSES")
    NEW_MESSAGE_TIMEOUT = int(os.getenv("TIMEOUT_WS_NEW_MESSAGE"))
    MAX_MESSAGE_TIMEOUT = int(os.getenv("TIMEOUT_WS_MAX_WAIT"))
    LOG_FILE = LogRecord(os.getenv("PATH_WS_LOG"))

    asyncio.run(main(
        os.getenv("WEBSOCKET_IP"),
        int(os.getenv("WEBSOCKET_PORT")),
        os.getenv("REDIS_IP"),
        int(os.getenv("REDIS_PORT")),
        os.getenv("MSSQL_HOST"),
        os.getenv("MSSQL_USER"),
        os.getenv("MSSQL_PASS"),
        os.getenv("MSSQL_DATA"),
        os.getenv("MSSQL_TABL"),
        args.insert,
        args.receive
    ))

    LOG_FILE.close()