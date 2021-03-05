import asyncio

def unasyncio(method):
    return asyncio.get_event_loop().run_until_complete(method)
