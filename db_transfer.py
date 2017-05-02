#!/usr/bin/python
# -*- coding: UTF-8 -*-

import logging
import time
from server_pool import ServerPool
import traceback
from shadowsocks import common, shell, lru_cache, obfs
from configloader import load_config, get_config
import importloader

switchrule = None
db_instance = None


class DbTransfer(object):
    def __init__(self):
        import threading
        self.event = threading.Event()
        self.key_list = ['port', 'u', 'd', 'transfer_enable', 'passwd', 'enable']
        self.last_get_transfer = {}  # 上一次的实际流量
        self.last_update_transfer = {}  # 上一次更新到的流量（小于等于实际流量）
        self.force_update_transfer = set()  # 强制推入数据库的ID
        self.port_uid_table = {}  # 端口到uid的映射（仅v3以上有用）
        self.onlineuser_cache = lru_cache.LRUCache(timeout=60 * 30)  # 用户在线状态记录
        self.pull_ok = False  # 记录是否已经拉出过数据
        self.mu_ports = {}
        self.user_pass = {}  # 记录更新此用户流量时被跳过多少次

    def update_all_user(self, dt_transfer):
        logging.info('update_all_user')
        update_transfer = {}

        query_head = 'UPDATE user'
        query_sub_when = ''
        query_sub_when2 = ''
        query_sub_in = None
        last_time = time.time()

        for id in dt_transfer.keys():
            transfer = dt_transfer[id]
            # 小于最低更新流量的先不更新
            update_trs = 1024 * (2048 - self.user_pass.get(id, 0) * 64)
            if transfer[0] + transfer[1] < update_trs and id not in self.force_update_transfer:
                self.user_pass[id] = self.user_pass.get(id, 0) + 1
                continue
            if id in self.user_pass:
                del self.user_pass[id]

            update_transfer[id] = transfer

            traffic = 'the port ' + str(id) + ' use' + self.traffic_format(transfer[0] + transfer[1])

            logging.info(traffic)

        return update_transfer

    def pull_db_all_user(self):
        '''
        :return: 获得用户信息
        '''
        logging.info('pull_db_all_user')
        # 测试用的两个用户信息
        rows = [{'enable': 1, 'd': 8888719L, 'passwd': u'gfzC8h', 'transfer_enable': 5467275264L,
                 'u': 117218L, 'port': 1025L},
                {'enable': 1, 'd': 2112637L, 'passwd': u'b5QiRt', 'transfer_enable': 5368709120L, 'u': 8752L,
                 'port': 1026L}]

        if not rows:
            logging.warn('no user in db')
        return rows

    def push_db_all_user(self):
        logging.info('push_db_all_user')
        if self.pull_ok is False:
            return
        # 更新用户流量到数据库
        last_transfer = self.last_update_transfer
        curr_transfer = ServerPool.get_instance().get_servers_transfer()
        # 上次和本次的增量
        dt_transfer = {}
        for id in self.force_update_transfer:  # 此表中的用户统计上次未计入的流量
            if id in self.last_get_transfer and id in last_transfer:
                dt_transfer[id] = [self.last_get_transfer[id][0] - last_transfer[id][0],
                                   self.last_get_transfer[id][1] - last_transfer[id][1]]

        for id in curr_transfer.keys():
            if id in self.force_update_transfer or id in self.mu_ports:
                continue
            # 算出与上次记录的流量差值，保存于dt_transfer表
            if id in last_transfer:
                if curr_transfer[id][0] + curr_transfer[id][1] - last_transfer[id][0] - last_transfer[id][1] <= 0:
                    continue
                dt_transfer[id] = [curr_transfer[id][0] - last_transfer[id][0],
                                   curr_transfer[id][1] - last_transfer[id][1]]
            else:
                if curr_transfer[id][0] + curr_transfer[id][1] <= 0:
                    continue
                dt_transfer[id] = [curr_transfer[id][0], curr_transfer[id][1]]

            # 有流量的，先记录在线状态
            if id in self.last_get_transfer:
                if curr_transfer[id][0] + curr_transfer[id][1] > self.last_get_transfer[id][0] + \
                        self.last_get_transfer[id][1]:
                    self.onlineuser_cache[id] = curr_transfer[id][0] + curr_transfer[id][1]
            else:
                self.onlineuser_cache[id] = curr_transfer[id][0] + curr_transfer[id][1]

        self.onlineuser_cache.sweep()

        update_transfer = self.update_all_user(dt_transfer)  # 返回有更新的表
        for id in update_transfer.keys():  # 其增量加在此表
            if id not in self.force_update_transfer:  # 但排除在force_update_transfer内的
                last = self.last_update_transfer.get(id, [0, 0])
                self.last_update_transfer[id] = [last[0] + update_transfer[id][0], last[1] + update_transfer[id][1]]
        self.last_get_transfer = curr_transfer
        for id in self.force_update_transfer:
            if id in self.last_update_transfer:
                del self.last_update_transfer[id]
            if id in self.last_get_transfer:
                del self.last_get_transfer[id]
        self.force_update_transfer = set()

    def del_server_out_of_bound_safe(self, last_rows, rows):
        logging.info('del_server_out_of_bound_safe')
        # 停止超流量的服务
        # 启动没超流量的服务
        cur_servers = {}
        new_servers = {}
        allow_users = {}
        mu_servers = {}
        for row in rows:
            try:
                allow = row['enable'] == 1 and row['u'] + row['d'] < row['transfer_enable']
            except Exception as e:
                allow = False

            port = row['port']
            passwd = common.to_bytes(row['passwd'])
            if hasattr(passwd, 'encode'):
                passwd = passwd.encode('utf-8')
            cfg = {'password': passwd}
            if 'id' in row:
                self.port_uid_table[row['port']] = row['id']

            read_config_keys = ['method', 'obfs', 'obfs_param', 'protocol', 'protocol_param', 'forbidden_ip',
                                'forbidden_port', 'speed_limit_per_con', 'speed_limit_per_user']
            for name in read_config_keys:
                if name in row and row[name]:
                    cfg[name] = row[name]

            merge_config_keys = ['password'] + read_config_keys
            for name in cfg.keys():
                if hasattr(cfg[name], 'encode'):
                    try:
                        cfg[name] = cfg[name].encode('utf-8')
                    except Exception as e:
                        logging.warning('encode cfg key "%s" fail, val "%s"' % (name, cfg[name]))

            if port not in cur_servers:
                cur_servers[port] = passwd
            else:
                logging.error('more than one user use the same port [%s]' % (port,))
                continue

            if allow:
                allow_users[port] = passwd
                if 'protocol' in cfg and 'protocol_param' in cfg and common.to_str(
                        cfg['protocol']) in obfs.mu_protocol():
                    if '#' in common.to_str(cfg['protocol_param']):
                        mu_servers[port] = passwd
                        del allow_users[port]

                cfgchange = False
                if port in ServerPool.get_instance().tcp_servers_pool:
                    relay = ServerPool.get_instance().tcp_servers_pool[port]
                    for name in merge_config_keys:
                        if name in cfg and not self.cmp(cfg[name], relay._config[name]):
                            cfgchange = True
                            break
                if not cfgchange and port in ServerPool.get_instance().tcp_ipv6_servers_pool:
                    relay = ServerPool.get_instance().tcp_ipv6_servers_pool[port]
                    for name in merge_config_keys:
                        if name in cfg and not self.cmp(cfg[name], relay._config[name]):
                            cfgchange = True
                            break

            if port in mu_servers:
                if ServerPool.get_instance().server_is_run(port) > 0:
                    if cfgchange:
                        logging.info('db stop server at port [%s] reason: config changed: %s' % (port, cfg))
                        ServerPool.get_instance().cb_del_server(port)
                        self.force_update_transfer.add(port)
                        new_servers[port] = (passwd, cfg)
                else:
                    self.new_server(port, passwd, cfg)
            else:
                config = shell.get_config(False)
                if ServerPool.get_instance().server_is_run(port) > 0:
                    if config['additional_ports_only'] or not allow:
                        logging.info('db stop server at port [%s]' % (port,))
                        ServerPool.get_instance().cb_del_server(port)
                        self.force_update_transfer.add(port)
                    else:
                        if cfgchange:
                            logging.info('db stop server at port [%s] reason: config changed: %s' % (port, cfg))
                            ServerPool.get_instance().cb_del_server(port)
                            self.force_update_transfer.add(port)
                            new_servers[port] = (passwd, cfg)

                elif not config[
                    'additional_ports_only'] and allow and port > 0 and port < 65536 and ServerPool.get_instance().server_run_status(
                    port) is False:
                    self.new_server(port, passwd, cfg)

        for row in last_rows:
            if row['port'] in cur_servers:
                pass
            else:
                logging.info('db stop server at port [%s] reason: port not exist' % (row['port']))
                ServerPool.get_instance().cb_del_server(row['port'])
                self.clear_cache(row['port'])
                if row['port'] in self.port_uid_table:
                    del self.port_uid_table[row['port']]

        if len(new_servers) > 0:
            from shadowsocks import eventloop
            self.event.wait(eventloop.TIMEOUT_PRECISION + eventloop.TIMEOUT_PRECISION / 2)
            for port in new_servers.keys():
                passwd, cfg = new_servers[port]
                self.new_server(port, passwd, cfg)

        logging.debug('db allow users %s \nmu_servers %s' % (allow_users, mu_servers))
        for port in mu_servers:
            ServerPool.get_instance().update_mu_users(port, allow_users)

        self.mu_ports = mu_servers

    def clear_cache(self, port):
        if port in self.force_update_transfer: del self.force_update_transfer[port]
        if port in self.last_get_transfer: del self.last_get_transfer[port]
        if port in self.last_update_transfer: del self.last_update_transfer[port]

    def new_server(self, port, passwd, cfg):
        protocol = cfg.get('protocol', ServerPool.get_instance().config.get('protocol', 'origin'))
        method = cfg.get('method', ServerPool.get_instance().config.get('method', 'None'))
        obfs = cfg.get('obfs', ServerPool.get_instance().config.get('obfs', 'plain'))
        logging.info('db start server at port [%s] pass [%s] protocol [%s] method [%s] obfs [%s]' % (
            port, passwd, protocol, method, obfs))
        ServerPool.get_instance().new_server(port, cfg)

    def cmp(self, val1, val2):
        if type(val1) is bytes:
            val1 = common.to_str(val1)
        if type(val2) is bytes:
            val2 = common.to_str(val2)
        return val1 == val2

    @staticmethod
    def del_servers():
        for port in [v for v in ServerPool.get_instance().tcp_servers_pool.keys()]:
            if ServerPool.get_instance().server_is_run(port) > 0:
                ServerPool.get_instance().cb_del_server(port)
        for port in [v for v in ServerPool.get_instance().tcp_ipv6_servers_pool.keys()]:
            if ServerPool.get_instance().server_is_run(port) > 0:
                ServerPool.get_instance().cb_del_server(port)

    @staticmethod
    def thread_db():
        '''
        :param obj: 就是DbTransfer
        
        线程的入口函数
        '''
        logging.info('thread_db')
        import socket
        global db_instance
        timeout = 60
        socket.setdefaulttimeout(timeout)
        last_rows = []
        db_instance = DbTransfer()
        ServerPool.get_instance()
        shell.log_shadowsocks_version()

        try:
            import resource
            logging.info(
                'current process RLIMIT_NOFILE resource: soft %d hard %d' % resource.getrlimit(resource.RLIMIT_NOFILE))
        except:
            pass
        rows = db_instance.pull_db_all_user()
        try:
            while True:
                load_config()
                logging.info('while True')
                try:
                    db_instance.push_db_all_user()
                    if rows:
                        db_instance.pull_ok = True
                        config = shell.get_config(False)
                        for port in config['additional_ports']:
                            val = config['additional_ports'][port]
                            val['port'] = int(port)
                            val['enable'] = 1
                            val['transfer_enable'] = 1024 ** 7
                            val['u'] = 0
                            val['d'] = 0
                            if "password" in val:
                                val["passwd"] = val["password"]
                            rows.append(val)
                    db_instance.del_server_out_of_bound_safe(last_rows, rows)
                    last_rows = rows
                except Exception as e:
                    trace = traceback.format_exc()
                    logging.error(trace)
                # logging.warn('db thread except:%s' % e)
                if db_instance.event.wait(get_config().UPDATE_TIME) or not ServerPool.get_instance().thread.is_alive():
                    break
        except KeyboardInterrupt as e:
            pass
        db_instance.del_servers()
        ServerPool.get_instance().stop()
        db_instance = None

    @staticmethod
    def thread_db_stop():
        global db_instance
        db_instance.event.set()

    def traffic_format(self, traffic):
        if traffic < 1024 * 8:
            return str(int(traffic)) + "B";

        if traffic < 1024 * 1024 * 2:
            return str(round((traffic / 1024.0), 2)) + "KB";

        return str(round((traffic / 1048576.0), 2)) + "MB";
