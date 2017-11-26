#!/usr/bin/env python

# encoding: utf-8

'''

@author: lion

@file: orm.py

@time: 2017/11/26 15:19

@desc:

'''

import  asyncio,aiomysql,logging

def log(sql,args=()):
    logging.info('SQL:%s' % sql)

#创建数据库连接池
async def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host','localhost'),
        port=kw.get('port',3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset','utf8'),
        autocommit=kw.get('autocommit',True),
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop
    )

async def select(sql,args,size=None):
    log(sql,args)
    global __pool
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(sql.replace('?','%s'),args or )