#!/usr/bin/env python3.7

# TODO copyright
# TODO docs

import asyncio
import functools
import logging
import random
import string
import uuid

import attr


logging.basicConfig(
    format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO
)

@attr.s
class PubSubMessage:
    msg_id = attr.ib(repr=False)
    instance_name = attr.ib()
    hostname = attr.ib(repr=False, init=False)

    def __attrs_post_init__(self):
        self.hostname = f'{self.instance_name}.example.net'

async def produce(queue):
    while True:
        msg_id = str(uuid.uuid4())
        host_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        instance_name = f'cattle-{host_id}'
        msg = PubSubMessage(msg_id=msg_id, instance_name=instance_name)
        # produce an item
        logging.info(f'Published message {msg}')
        # put the item in the queue
        await queue.put(msg)
        # simulate randomness of publishing messages
        await asyncio.sleep(random.random())

async def restart_host(message):
    # unhelpful simulation of i/o work
    await asyncio.sleep(random.random())
    logging.info(f'Restarted {message.hostname}')

async def save(message):
    # unhelpful simulation of i/o work
    await asyncio.sleep(random.random())
    logging.info(f'Saved {message} into database')

def cleanup(message, future):
    logging.info(f'Done. Acked {message}')

async def pull_message(queue):
    message = await queue.get()
    logging.info(f'Pulled {message}')

    save_coro = save(message)
    restart_coro = restart_host(message)

    await asyncio.gather(save_coro, restart_coro)

    callback = functools.partial(cleanup, message)
    coros.add_done_callback(callback)
    await coros

async def consume(queue):
    coroutines = set()
    while True:
        coro = pull_message(queue)
        coroutines.add(coro)
        _, coroutines = await asyncio.wait(coroutines, timeout=1)

if __name__ == '__main__':
    queue = asyncio.Queue()
    producer_coro = produce(queue)
    consumer_coro = consume(queue)

    loop = asyncio.get_event_loop()
    try:
        loop.create_task(producer_coro)
        loop.create_task(consumer_coro)
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info('Interrupted')
    finally:
        logging.info('Cleaning up')
        loop.stop()
