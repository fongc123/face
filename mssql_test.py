"""
FILE: mssql_test.py

DESCRIPTION: Manual test for MSSQL database.
"""

import pymssql
from argparse import ArgumentParser
import random
import string
import datetime
import json
import time

SERVER = "localhost"
USER = "sa"
PASSWORD = "mystrongPassword123"
DATABASE = "tempdb"

connection = pymssql.connect(SERVER, USER, PASSWORD, DATABASE)
cursor = connection.cursor()

def generate_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))

if __name__ == "__main__":
    parser = ArgumentParser(description='Test MSSQL connection.')
    parser.add_argument("--create_table", action="store_true", help="Create table.")
    parser.add_argument("--insert", action="store_true", help="Insert data to MSSQL database.")
    parser.add_argument("--insert_json", action="store_true", help="Insert JSON data to MSSQL database.")
    parser.add_argument("--view", action="store_true", help="View data from MSSQL database.")
    parser.add_argument("--delete", action="store_true", help="Delete table from MSSQL database.")
    parser.add_argument("--view_tables", action="store_true", help="View tables from MSSQL database.")
    parser.add_argument("--view_messages", action="store_true", help="View messages from MSSQL database.")
    args = parser.parse_args()

    SQL_TABLE = "G3TRANS"

    if args.create_table:
        _script_create_table = f"""
        IF OBJECT_ID('{SQL_TABLE}', 'U') IS NOT NULL
            DROP TABLE {SQL_TABLE}
        CREATE TABLE {SQL_TABLE} (
            cmd VARCHAR(255),
            sn VARCHAR(255),
            enrollid INT,
            aliasid INT,
            name VARCHAR(255),
            time VARCHAR(255),
            mode INT,
            input INT,
            event INT
        )
        """

        cursor.execute(_script_create_table)
        connection.commit()
        print("Table created.")
    elif args.insert:
        _script_insert = f"""
        INSERT INTO {SQL_TABLE} (cmd, sn, enrollid, aliasid, name, time, mode, input, event) VALUES (%s, %s, %d, %d, %s, %s, %d, %d, %d)
        """

        cursor.executemany(
            _script_insert,
            [
                (
                    "sendlog", "1234567890", 1, 1, generate_random_string(10), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                    1, 1, 1
                ) for _ in range(100)
            ]
        )

        connection.commit()
    elif args.insert_json:
        with open("./responses/sendlog.json", "r") as f:
            data = json.load(f)
            cursor.executemany(
                f"INSERT INTO {SQL_TABLE} VALUES (%s, %s, %d, %d, %s, %s, %d, %d, %d)",
                [
                    (
                        data["cmd"],
                        data["sn"],
                        data['record'][i]["enrollid"],
                        data['record'][i]["aliasid"],
                        data['record'][i]["name"],
                        data['record'][i]["time"],
                        data['record'][i]["mode"],
                        data['record'][i]["inout"],
                        data['record'][i]["event"]
                    ) for i in range(data["count"])
                ]
            )

            connection.commit()
    elif args.view:
        _script_view_table = f"""
        IF OBJECT_ID('{SQL_TABLE}', 'U') IS NOT NULL
            SELECT * FROM {SQL_TABLE}
        ELSE
            PRINT 'Table does not exist.'
        """
        cursor.execute(_script_view_table)
        row = cursor.fetchone()
        while row:
            print(row)
            row = cursor.fetchone()
    elif args.delete:
        _script_delete_table = f"""
        IF OBJECT_ID('{SQL_TABLE}', 'U') IS NOT NULL
            DROP TABLE {SQL_TABLE}
        ELSE
            PRINT 'Table does not exist.'
        """

        cursor.execute(_script_delete_table)
        connection.commit()
    elif args.view_tables:
        _script_view_tables = f"""
        SELECT * FROM sys.tables
        """
        cursor.execute(_script_view_tables)
        row = cursor.fetchone()
        while row:
            print(row)
            row = cursor.fetchone()
    elif args.view_messages:
        _script_view_messages = f"""
        SELECT * FROM sys.messages WHERE language_id = 1033
        """
        cursor.execute(_script_view_messages)
        row = cursor.fetchone()
        while row:
            print(row)
            row = cursor.fetchone()