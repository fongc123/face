"""
FILE: app_http.py

DESCRIPTION: HTTP server for sending commands to and receiving responses from AiFace device.

NOTES:
- This app only interacts with the Redis database.
- Redis database should contain two keys for `OUT` (sending to device) and `IN` (receiving from device) (WIP).

KNOWN ISSUES:
- Multiple HTTP calls to the same endpoint, to the same device (i.e., same Redis key), and at the same time may result in incorrect return responses.
    - Possible solution: Use a queue to ensure that only one HTTP call is processed at a time.
"""

from flask import Flask, request, jsonify
import redis
import json
from threading import Lock
import time
from argparse import ArgumentParser
import os

app = Flask(__name__)
lock = Lock()

@app.route("/", methods=["GET"])
def index():
    return "wassup"

@app.route("/admin/push", methods=["POST"])
def push():
    if request.headers.get("Authorization").split()[1] != AUTHORIZATION_KEY:
        return jsonify({"status" : "Incorrect authorization."}), 401

    data = request.get_json()
    if data is None or data == {} or not "sn" in data.keys() or not "cmd" in data.keys():
        return jsonify({"status" : "Incomplete or incorrect data."}), 400
    else:
        # Lock to ensure that only one HTTP call is processed at a time.
        while lock.locked():
            time.sleep(LOCK_TIMEOUT)
        lock.acquire()

        outgoing_key = f"{REDIS_DB_PREFIX}_{data['sn']}_{REDIS_OUTGOING_KEY}"
        try:
            # dump data to Redis
            r = redis.Redis(host=REDIS_IP, port=REDIS_PORT, db=0)
            r.rpush(outgoing_key, json.dumps(data))

            # wait for response
            start_time = time.time()
            while True:
                response = r.lpop(f"{REDIS_DB_PREFIX}_{data['sn']}_{REDIS_INCOMING_KEY}")
                if data['cmd'] == 'reboot':
                    response = '{"status" : "No response."}'
                if response is not None or time.time() - start_time >= WAIT_RESPONSE_TIMEOUT:
                    break

            if response is not None:
                return jsonify(json.loads(response)), 200
            else:
                raise Exception("No response.")
        except Exception as e:
            status_str = f"{str(e)}"
            r.delete(outgoing_key)

            return jsonify({"status" : status_str}), 500
        finally:
            lock.release()
    
if __name__ == "__main__":
    parser = ArgumentParser(description='HTTP server for AiFace device.')
    parser.add_argument("--env", type=str, default="../.env", help="Config stored in an environment file.")
    args = parser.parse_args()

    FLASK_IP = os.getenv("FLASK_IP")
    FLASK_PORT = int(os.getenv("FLASK_PORT"))
    REDIS_IP = os.getenv("REDIS_IP")
    REDIS_PORT = int(os.getenv("REDIS_PORT"))
    REDIS_DB_PREFIX = os.getenv("REDIS_DB_PREFIX")
    REDIS_OUTGOING_KEY = os.getenv("REDIS_OUT_KEY")
    REDIS_INCOMING_KEY = os.getenv("REDIS_IN_KEY")
    AUTHORIZATION_KEY = os.getenv("FLASK_AUTHORIZATION_KEY")
    LOCK_TIMEOUT = int(os.getenv("TIMEOUT_HTTP_LOCK"))
    WAIT_RESPONSE_TIMEOUT = int(os.getenv("TIMEOUT_HTTP_WAIT_RESPONSE"))

    app.run(host=FLASK_IP, port=FLASK_PORT, debug=True)