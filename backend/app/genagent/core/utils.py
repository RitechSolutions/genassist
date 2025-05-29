import asyncio
import concurrent.futures
from typing import Callable
def run_async_function(main, run_in_new_loop = True, callback: Callable = None, *args, **kwargs ):
    """
    Run an async function, handling different environments (with or without existing event loop).
    
    Args:
        main: The async function to run
        run_in_new_loop: If False, run in current loop and block until result is available
        callback: A callback function to call with the result of the async function
        *args: Positional arguments to pass to the async function
        **kwargs: Keyword arguments to pass to the async function
    
    Returns:
        The result of the async function
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 'RuntimeError: There is no current event loop...'
        loop = None

    if loop and loop.is_running() and not run_in_new_loop:
        print('Async event loop already running. Running coroutine and waiting for result...')
        # Use run_coroutine_threadsafe to properly block and get the result
        future = asyncio.run_coroutine_threadsafe(main(*args, **kwargs), loop)
        # This will block until the result is available
        try:
            result = future.result()
            print(f'Task done with result={result}')
            return result
        except Exception as e:
            print(f'Task failed with exception: {e}')
            raise e
    elif loop and loop.is_running() and run_in_new_loop:
        print('Async event loop already running. Adding coroutine to the event loop.')
        tsk = loop.create_task(main(*args, **kwargs))
        # ^-- https://docs.python.org/3/library/asyncio-task.html#task-object
        # Optionally, a callback function can be executed when the coroutine completes
        tsk.add_done_callback(
            lambda t: print(f'Task done with result={t.result()}  << return val of main()'))
        return tsk
    elif loop and loop.is_running() and run_in_new_loop and callback:
        print('Async event loop already running. Adding coroutine to the event loop.')
        tsk = loop.create_task(main(*args, **kwargs))
        # ^-- https://docs.python.org/3/library/asyncio-task.html#task-object
        # Optionally, a callback function can be executed when the coroutine completes
        tsk.add_done_callback(
            lambda t: callback(t.result()))
        return tsk
    else:
        print('Starting new event loop')
        result = asyncio.run(main(*args, **kwargs))
        return result