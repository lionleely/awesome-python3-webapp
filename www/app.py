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
from jinja2 import Environment,FileSystemLoader
# from handler import

logging.basicConfig(level=logging.INFO)

# 初始化jinjia2模板环境
def init_jinja2(app,**kw):
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
    # 获取模板文件夹路径
    path = kw.get('path',None)
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
    # Environment类是jinja2的核心类，用来保存配置、全局对象以及模板文件的路径
    # FileSystemLoader类加载path路径中的模板文件
    env = Environment(loader=FileSystemLoader(path), **options)
    # 过滤器集合
    filters = kw.get('filters',None)
    if filters:
        for name, f in filters.items():
            # filters 是Environment类的属性：过滤器字典
            env.filters[name] = f
    # 所有的一切是为了给APP添加__templating__字段
    # 前面讲jinja2的环境配置都赋值给env了，这里再把env存入APP的dict中，这样APP就知道要到哪儿去找模板，怎么解析末班
    app['__template__'] = env # app是一个dict-like对象

# 编写一个过滤器
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta//60)
    if delta < 86400:
        return u'%s小时前' % (delta//3600)
    if delta <604800:
        return u'%s天前' % (delta//86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

# 编写用于输出日志的middleware
# handler是视图函数
async def logger_factory(app,handler):
    async def logger(request):
        logging.info('Request:%s %s' % (request.method, request.path))
        return await handler(request)
    return logger

# 处理视图函数返回值，制作response的middleware
# 请求对象request的处理工序：
#              logger_factory => response_factory => RequestHandler().__call__ => handler
# 响应对象response的处理工序：
# 1、由视图函数处理request后返回数据
# 2、@get@post装饰器在返回对象上附加'__method__'和'__route__'属性，使其附带URL信息
# 3、response_factory对处理后的对象，经过一系列类型判断，构造出真正的web.Response对象
async def response_factory(app,handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        logging.info('response result = %s' % str(r))
        if isinstance(r, web.StreamResponse):# StreamResponse 是所有response对象的父类
            return r
        if isinstance(r,bytes):
            logging.info('*'*10)
            resp = web.Response(body=r) # 继承自StreamResponse，接受body参数，构造HTTP响应内容
            # Response的content type属性
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r,str):
            if r.startswith('redirect'):# 若返回重定向字符串
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8' # utf-8编码的text格式
            return resp
        # r为dict对象时
        if isinstance(r,dict):
            # 在后续构造视图函数返回值时，会加入__template__值，用以选择渲染的模板
            template = r.get('__template__',None)
            if template is None:# 不带模板信息，返回json对象
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda obj:obj.__dict__).encode('utf-8'))
                # ensure_ascii:默认TRUE，仅能输出ASCII格式数据。所以设置为FALSE
                # default:r对象会先被传入default中的函数进行处理，然后才被序列化为json对象
                # __dict__:以dict形式返回对象属性和值的映射
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:# 带模板信息，渲染模板
                # app['__templating__']获取已初始化的Environment对象，调用get_template()方法返回Template对象
                # 调用Template对象的render（）方法，传入r渲染模板，返回Unicode格式字符串，将其用utf-8编码
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r))
                resp.content_type = 'text/html;charset=utf-8'# utf-8编码的HTML格式
                return resp
        # 返回响应码
        if isinstance(r,int) and (600>r>100):
            resp = web.Response(status=r)
            return resp
        # 返回了一组响应代码和原因，如：（200，'OK'），（404，’Not Found‘）
        if isinstance(r, tuple) and len(r) == 2:
            status_code, message = r
            if isinstance(status_code,int) and (600>status_code>100):
                resp = web.Response(status=r,text=str(message))
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

# def auth_factory(app, handler):
#     async def auth(request):
#         logging.info('check user:%s %s' % (request.method,request.path))
#         request.__user__ = None
#         # request的cookies属性中保存所有cookie值
#         cookie_str = request.cookies.get(COOKIE_NAME,None)



