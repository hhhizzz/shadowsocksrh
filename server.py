#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2015 breakwall
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import json
import socket
import threading
import os
import logging.config
import logging
import time
import datetime

if __name__ == '__main__':
    import inspect

    os.chdir(os.path.dirname(os.path.realpath(inspect.getfile(inspect.currentframe()))))

import db_transfer
from shadowsocks import shell


class ChildTHread(threading.Thread):
    def __init__(self, obj):
        super(ChildTHread, self).__init__()
        self.obj = obj()

    def run(self):
        self.obj.thread_db()

    def stop(self):
        self.obj.thread_db_stop()


class MainThread(threading.Thread):
    def __init__(self):
        super(MainThread, self).__init__()
        self.daemon = True

    def run(self):
        thread = ChildTHread(db_transfer.DbTransfer)
        thread.start()
        host = 'localhost'
        s = socket.socket()
        port = 8089
        s.bind((host, port))
        s.listen(1)
        while True:
            c, addr = s.accept()
            # 接收浏览器的请求, 不作处理
            data = c.recv(1024)
            form = data.split('\r\n')
            entry = form[-1]  # main content of the request
            logging.debug(entry)
            logging.info(data)
            data = {'cmd': 4}
            if data['cmd'] == 0:
                thread.stop()
                now = datetime.datetime.utcnow()
                content = '{"ok":1}'
                expires = datetime.timedelta(days=1)
                GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
                response = '''HTTP/1.1 200 OK
                Server: "shadowsocksrh
                Date: %s
                Expires: %s
                Content-Type: text/html;charset=utf8
                Content-Length: %s
                Connection: keep-alive

                %s''' % (
                    now.strftime(GMT_FORMAT),
                    (now + expires).strftime(GMT_FORMAT),
                    len(content),
                    content
                )
                # 发送回应
                c.send(response)
                c.close()
                s.close()
                logging.info("the ssserver is stop by main server")
                exit()
            elif data['cmd'] == 4:
                now = datetime.datetime.utcnow()
                content = '{"ok":1}'
                expires = datetime.timedelta(days=1)
                GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
                response = '''HTTP/1.1 200 OK
                Server: "shadowsocksrh
                Date: %s
                Expires: %s
                Content-Type: text/html;charset=utf8
                Content-Length: %s
                Connection: keep-alive

                %s''' % (
                    now.strftime(GMT_FORMAT),
                    (now + expires).strftime(GMT_FORMAT),
                    len(content),
                    content
                )
                # 发送回应
                c.send(response)
                c.close()
                logging.info("the ssserver is reboot by main server")
                thread.stop()
                thread.join(1)
                thread = ChildTHread(db_transfer.DbTransfer)
                time.sleep(5.0)
                thread.start()


def main():
    shell.check_python()
    # 设置logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename='log.txt',
                        filemode='a')

    thread = MainThread()

    thread.start()
    try:
        while thread.is_alive():
            thread.join(10.0)
    except (KeyboardInterrupt, IOError, OSError) as e:
        import traceback
        traceback.print_exc()
        thread.stop()


if __name__ == '__main__':
    main()
