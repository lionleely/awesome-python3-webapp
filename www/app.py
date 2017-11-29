#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2017/11/23 16:53
# @Author   :  lion
# @Site     : 
# @File     : app.py
# @Software : PyCharm

import logging

import asyncio,os,json,time
from datetime import datetime
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# 初始化jinjia2模板环境
def init_jinjia2(app,**kw):
    logging.info('init jinjia2...')
    # class Environment(**options)
    # 配置options参数
    options = dict(
        autoescape = kw.get('autoescape',True),
        # 代码块的开始、结束标志
        block_start_string = kw.get('block_start_string','{%'),
        block_end_string = kw.get('block_end_string','%}'),
        # 变量的开始、结束标志
        variable_start_string = kw.get('variable_start_string','{{'),
        variable_end_string = kw.get('variable_end_string','}}'),
        # 自动加载修改后的模板文件
        auto_reload = kw.get('auto_reload',True)

    )