# -*- coding: UTF-8 -*-
# Config 程序更新时间,单位秒

UPDATE_TIME = 10

# http 获取失败重试次数 超过次数便退出程序

FAIL_TIMES = 3

# 允许最多的用户数
MAX_USERS = 20

# 用于获取用户的属性
ID = '39'

KEY = 'test'

ADDRESS = '47.52.6.38'

HTTPS = False

HTTPLOG = True

# 是否输出调试信息
debug = False


#***********************************分割线*****************************************#

if HTTPS:
    SERVER_ADDRESS = r'https://' + ADDRESS + r'/Api/Index/fetchUser' + '?id=' + ID + "&key=" + KEY
    POST_ADDRESS = r'https://' + ADDRESS + r'/Api/Index/update' + '?id=' + ID + "&key=" + KEY
else:
    SERVER_ADDRESS = r'http://' + ADDRESS + r'/Api/Index/fetchUser' + '?id=' + ID + "&key=" + KEY
    POST_ADDRESS = r'http://' + ADDRESS + r'/Api/Index/update' + '?id=' + ID + "&key=" + KEY
LOG_URL = r'/Api/Index/log' + '?id=' + ID + "&key=" + KEY
