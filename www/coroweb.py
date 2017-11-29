#!/usr/bin/env python

# encoding: utf-8

# @author: lion

# @file: coroweb.py

# @time: 2017/11/26 15:19

# @desc:

import functools, inspect, asyncio, os
import logging
from urllib import parse
from www.apis import APIError



from aiohttp import web, asyncio


def Handler_decorator(path, *, method):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__route__ = path
        wrapper.__method__ = method
        return wrapper
    return decorator


get = functools.partial(Handler_decorator, method='GET')
post = functools.partial(Handler_decorator, method='POST')


# 使用inspect模块，检查视图函数的参数

# inspect.Parameter.kind类型：
# POSITIONAL_ONLY         未知参数
# KEYWORD_ONLY            命名关键词参数
# VAR_POSITIONAL          可选参数*args
# VAR_KEYWORD             关键词参数**kw
# POSITIONAL_OR_KEYWORD   位置或必选参数

# 获取无默认值的命名关键词参数
def get_required_kw_args(fn):
    args = []


    params = inspect.signature(fn).parameters
    for name,param in params.item():
        # 如果视图函数存在命名关键字参数，且默认值为空，获取它的key(参数名)
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


# 获取命名关键词参数
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

# 判断是否有命名关键词参数
def has_named_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# 判断是否有关键词参数
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# 判断是否含有名叫‘request’的参数，且位置在最后
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = inspect.signature(fn).parameters
    found = False
    for name,param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and
                      param.kind != inspect.Parameter.KEYWORD_ONLY   and
                      param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function:%s%s' % (fn.__name__, str(sig)))
    return found

# 定义RequestHandler从视图函数中分析其需要接受的参数，从web.Request中获取必要的参数
# 调用视图函数，然后把结果转换为web.Response对象，符合aiohttp框架要求
class RequestHandler(object):
    def __init__(self,app,fn):
        self._app = app
        self._func = fn
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._has_request_arg = has_request_arg(fn)
        self._has_named_kw_arg = has_named_kw_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)

        # 1.定义kw，用于保存参数
        # 2.判断视图函数是否存在关键词参数，如果存在根据POST或者GET方法将request请求内容保存到kw
        # 3.如果kw为空（说明request无请求内容），则将match_info列表里的资源映射给kw；若不为空，把命名关键词参数内容给kw
        # 4.完善_has_request_arg和_required_kw_args属性
        async def __call__(self, request):
            kw = None #定义kw,用于保存request中参数
            if self._has_named_kw_arg or self._has_var_kw_arg:
                if request.method == 'POST':
                    if request.content_type ==None:
                        return web.HTTPBadRequest(text='Missing Content_type.')
                    ct = request.content_type.lower()
                    if ct.startswith('application/json'):
                        params = await request.json()
                        if not isinstance(params,dict):
                            return web.HTTPBadRequest(text='JSON body must be object.')
                        kw = params
                    elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                        params = await request.post()
                        kw = dict(**params)
                    else:
                        return web.HTTPBadRequest(text='Unsupported Content-Type:%s' % request.content_type)

                if request.method == 'GET':
                    qs = request.query_string #返回URL查询语句，？后的键值。string形式
                    if qs:
                        kw = dict()
                        for k,v in parse.parse_qs(qs,True).item():
                            kw[k] = v[0]
            if kw is None:
                # 若request中无参数
                # request.match_info返回dict对象，可变路由中的可变字段{variable}为参数名，传入request请求的path为值
                # 若存在可变路由：/a/{name}/c,可匹配path为：/a/jack/c的request
                # 则request.match_info返回{name = jack}
                kw = dict(**request.match_info)
            else: # request 有参数
                if self._has_named_kw_arg and (not self._has_var_kw_arg):
                    copy = dict()
                    for name in self._named_kw_args:
                        if name in kw:
                            copy[name] = kw[name]
                    kw = copy
                for k,v in request.match_info.item():
                    if k in kw:
                        logging.warn('Duplicate arg name in named arg and kw args: %s' % k)
                    kw[k] = v
            if self._has_request_arg:
                kw['request'] = request
            if self._required_kw_args:
                for name in self._required_kw_args:
                    if not name in kw:
                        return web.HTTPBadRequest('Missing argument:%s' % name)

            # 至此，kw为视图函数fn真正能调用的参数
            # request请求中的参数，终于传递给了视图函数
            logging.info('call with args: %s' % str(kw))
            try:
                r=await self._func(**kw)
                return r
            except APIError as e:
                return dict(error=e.error, data=e.data, message=e.mesage)

# 编写一个add_route函数，用来注册一个视图函数
def add_route(app,fn):
    method = getattr(fn,'__method__',None)
    path = getattr(fn,'__route__',None)
    if method is None or path is None:
        raise ValueError('@get or @post not defined in %s.' % fn.__name__)
    # 判断URL处理函数是否协程并且是生成器
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        # 将fn转变成协程
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
    # 在APP中注册经RequestHandler类封装的视图函数
    app.router.add_route(method, path, RequestHandler(app, fn))

# 导入模块，批量注册视图函数
def add_routes(app,module_name):
    n = module_name.rfind('.')# 从右侧检索，返回索引。若无，返回-1.
    # 导入整个模块
    if n == -1:
        # __import__ 作用通import语句，但__import__是一个函数，并且只接受字符串作为参数
        # __import__('os',global(),locals(),['path','pip'],0),等价于from os import path,pip
        mod = __import__(module_name, globals(), locals, [], 0)
    else:
        name = module_name[(n+1):]
        # 只获取最终导入的模块，为后续调用dir()
        mod = getattr(__import__(module_name[:n],globals(),locals,[name], 0), name)
    for attr in dir(mod): # di()迭代出mod模块中所有的类，实例及函数等对象，str形式
        if attr.startswith('_'):
            continue # 忽略'_'开头的对象，直接继续for循环
        fn = getattr(mod,attr)
        # 确保是函数
        if callable(fn):
            # 确保视图函数存在method和path
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__path__', None)
            if method and path:
                # 注册
                add_route(app,fn)

# 添加静态文件，如image，css,javascript等
def add_static(app):
    # 拼接static文件目录
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

    app.router.add_static('/static/',path)
    logging.info('add static %s => %s' % ('/static/', path))




