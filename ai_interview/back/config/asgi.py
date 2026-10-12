"""ASGI config for the AI Interview backend."""

import os
import asyncio

from django.core.asgi import get_asgi_application
from asgiref.sync import sync_to_async


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_application = get_asgi_application()
from interviews.runtime import expire_sessions


async def watchdog():
    while True:
        await sync_to_async(expire_sessions, thread_sensitive=True)()
        await asyncio.sleep(5)


async def application(scope, receive, send):
    if scope['type'] == 'lifespan':
        monitor = None
        while True:
            event = await receive()
            if event['type'] == 'lifespan.startup':
                # 进程内巡检负责将无心跳会话终止为异常；关闭时取消任务。
                monitor = asyncio.create_task(watchdog())
                await send({'type': 'lifespan.startup.complete'})
            elif event['type'] == 'lifespan.shutdown':
                if monitor:
                    monitor.cancel()
                    await asyncio.gather(monitor, return_exceptions=True)
                await send({'type': 'lifespan.shutdown.complete'})
                return
    else:
        await django_application(scope, receive, send)
