"""
FILE: redis_manual.py

DESCRIPTION: Manually insert data into the Redis database for debugging.
"""

import redis
import json
import time
from argparse import ArgumentParser
import configparser

if __name__ == "__main__":
    parser = ArgumentParser(description='Websocket server for AiFace device.')
    parser.add_argument("--config", type=str, default="config.ini", help="Config file.")
    parser.add_argument("--data", type=str, default="test.json", help="Path to test data to send to device.")
    parser.add_argument('--send', action="store_true", help='Send message to Redis.')
    parser.add_argument('--view', action="store_true", help='View all messages in Redis.')
    parser.add_argument('--index', action="store_true", help='Last item in Redis list.') # the list key is hardcoded (device SN)
    parser.add_argument('--clear', action="store_true", help='Clear Redis list.')
    parser.set_defaults(send=False, view=False, index=False, clear=False)
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)

    REDIS_DB_PREFIX = config.get("REDIS", "DB_PREFIX").strip('"')
    REDIS_OUTGOING_KEY = config.get("REDIS", "OUT_KEY").strip('"')
    REDIS_INCOMING_KEY = config.get("REDIS", "IN_KEY").strip('"')
    DEVICE_SN = config.get("DEBUG", "DEVICE_SN").strip('"')

    r = redis.Redis(host='localhost', port=6379, db=0)

    if args.data is not None:
        data = json.load(open(args.data))
        if args.send:
            r.rpush(f"{REDIS_DB_PREFIX}_{DEVICE_SN}_{REDIS_OUTGOING_KEY}", json.dumps(data))
        elif args.view:
            cursor = '0'
            while cursor != 0:
                cursor, keys = r.scan(cursor=cursor)
                print(cursor, keys)
                for key in keys:
                    if r.type(key) == b'list':
                        elements = r.lrange(key, 0, -1)
                        for e in elements:
                            print(f"- {e.decode()}")
        elif args.index:
            list_key = f"{REDIS_DB_PREFIX}_{DEVICE_SN}_{REDIS_INCOMING_KEY}"
            last_item = json.loads(r.lindex(list_key, -1))
            print(last_item)
        elif args.clear:
            r.delete(f"{REDIS_DB_PREFIX}_{DEVICE_SN}_{REDIS_INCOMING_KEY}")