devinfo =  {
    "modelname": "AiFace",
    "usersize": 5000,
    "facesize": 5000,
    "fpsize": 0,
    "cardsize": 5000,
    "pwdsize": 5000,
    "logsize": 500000,
    "useduser": 4,
    "usedface": 3,
    "usedfp": 0,
    "usedcard": 3,
    "usedpwd": 0,
    "usedlog": 148,
    "usednewlog": 70,
    "netinuse": 1,
    "fpalgo": "thbio3.0",
    "firmware": "AiF43V_v4.40",
    "time": "2023-08-16 23:40:56",
    "mac": "00-01-A9-23-EA-6B"
}

# display certain key-value pairs in a string
def display_dict(d, keys):
    return ', '.join(f'{k}={d[k]}' for k in keys)

print(display_dict(devinfo, ['modelname', 'netinuse', 'fpalgo', 'firmware', 'time', 'mac']))