#!/usr/bin/python
# -*- coding: UTF-8 -*-
import importloader

g_config = None


def load_config():
    global g_config
    if g_config is None:
        g_config = importloader.loads(['userapiconfig'])
    return g_config


def get_config():
    return g_config


load_config()
