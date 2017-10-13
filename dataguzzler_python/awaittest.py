import sys
import asyncio

assert(sys.version_info >= (3,6))

async def foo():
    print("foo")
    pass

async def fubar():
    await foo_coro

def bar():
    print("bar")
    #await foo_coro
    return fubar()
    
if __name__ == "__main__":

    loop=asyncio.get_event_loop()
    foo_coro=foo()
    
    task=asyncio.ensure_future(bar())
    
    loop.run_until_complete(task);
    
    pass
