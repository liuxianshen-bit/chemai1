# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
import asyncio

cn_map = {'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','十':'0','零':'0'}
async def test():
    name = '高一(1)班'
    cn = ''.join(cn_map.get(c, c) for c in name)
    print(repr(name), repr(cn))
asyncio.run(test())
