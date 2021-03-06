#!/usr/bin/env python3.7

# calling blocking code

import asyncio
import concurrent.futures
import functools
import logging
import queue
import random
import signal
import string
import time
import uuid

import attr

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s,%(msecs)d %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
)


@attr.s
class PubSubMessage:
    msg_id = attr.ib(repr=False)
    instance_name = attr.ib()
    hostname = attr.ib(repr=False, init=False)

    def __attrs_post_init__(self):
        self.hostname = f'{self.instance_name}.example.net'

# required sync publisher for simulating a blocking,
# third-party consumer client
def publish_sync(queue_sync):
    msg_id = str(uuid.uuid4())
    choices = string.ascii_lowercase + string.digits
    host_id = ''.join(random.choices(choices, k=4))
    instance_name = f'cattle-{host_id}'
    msg = PubSubMessage(msg_id=msg_id, instance_name=instance_name)
    # publish an item
    logging.debug(f'Published message {msg}')
    # put the item in the queue
    queue_sync.put(msg)
    # simulate randomness of publishing messages
    time.sleep(random.random())

async def publish(executor, queue, loop):
    while True:
        coro = loop.run_in_executor(executor, publish_sync, queue)
        await asyncio.wait([coro], timeout=0.1)

async def restart_host(msg):
    # faked error
    rand_int = random.randrange(1, 3)
    if rand_int == 2:
        raise Exception(f'Could not restart {msg.hostname}')
    # unhelpful simulation of i/o work
    await asyncio.sleep(random.randrange(1,3))
    logging.info(f'Restarted {msg.hostname}')

async def save(msg):
    # unhelpful simulation of i/o work
    await asyncio.sleep(random.random())
    logging.info(f'Saved {msg} into database')

async def cleanup(msg, event):
    # this will block the rest of the coro until `event.set` is called
    await event.wait()
    # unhelpful simulation of i/o work
    await asyncio.sleep(random.random())
    logging.info(f'Done. Acked {msg}')

async def extend(msg, event):
    while not event.is_set():
        logging.info(f'Extended deadline by 3 seconds for {msg}')
        # want to sleep for less than the deadline amount
        await asyncio.sleep(2)

def handle_results(results):
    for result in results:
        if isinstance(result, Exception):
            logging.error(f'Caught exception: {result}')

async def handle_message(msg):
    event = asyncio.Event()

    save_coro = save(msg)
    restart_coro = restart_host(msg)

    asyncio.create_task(extend(msg, event))
    asyncio.create_task(cleanup(msg, event))

    results = await asyncio.gather(
        save_coro, restart_coro, return_exceptions=True
    )
    handle_results(results)
    event.set()

# simulates a blocking, third-party consumer client
def consume_sync(queue_sync):
    try:
        msg = queue_sync.get(block=False)
        logging.info(f'Pulled {msg}')
        return msg
    except queue.Empty:
        return

async def consume(executor, queue, loop):
    while True:
        msg = await loop.run_in_executor(executor, consume_sync, queue)
        if not msg:  # could be None
            continue
        asyncio.create_task(handle_message(msg))

async def handle_exception(fn, loop):
    try:
        await fn(loop)
    except asyncio.CancelledError:
        logging.info(f'Coroutine cancelled')
    except Exception as e:
        logging.error(f'Caught exception: {e}', exc_info=e)
    finally:
        loop.stop()

async def shutdown(signal, loop):
    logging.info(f'Received exit signal {signal.name}...')
    logging.info('Closing database connections')
    logging.info('Nacking outstanding messages')
    tasks = [t for t in asyncio.all_tasks() if t is not
             asyncio.current_task()]

    for i, task in enumerate(tasks):
        task.cancel()

    logging.info('Cancelling outstanding tasks')
    await asyncio.gather(*tasks)
    loop.stop()
    logging.info('Shutdown complete.')

if __name__ == '__main__':
    queue_sync = queue.Queue()
    loop = asyncio.get_event_loop()

    # May want to catch other signals too
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(s, loop)))

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    # publisher_coro = loop.run_in_executor(executor, publish_sync, queue)
    publisher_fn = functools.partial(publish, executor, queue_sync)
    consumer_fn = functools.partial(consume, executor, queue_sync)
    publisher_coro = handle_exception(publisher_fn, loop)
    consumer_coro = handle_exception(consumer_fn, loop)

    try:
        loop.create_task(publisher_coro)
        loop.create_task(consumer_coro)
        loop.run_forever()
    finally:
        logging.info('Cleaning up')
        loop.stop()
