#!/usr/bin/env python3.6

# TODO copyright
# TODO docs

# adapted from http://asyncio.readthedocs.io/en/latest/producer_consumer.html
import asyncio
import random

import attr

@attr.s
class PubSubMessage:
    msg_id = attr.ib()
    data = attr.ib()


async def produce(queue, n):
    for x in range(1, n + 1):
        msg = PubSubMessage(msg_id=x, data='Hello, world')
        # produce an item
        print('producing {} of {} messages'.format(x, n))
        # put the item in the queue
        await queue.put(msg)

    # indicate the producer is done
    await queue.put(None)


async def consume(queue):
    while True:
        # wait for an item from the producer
        msg = await queue.get()
        if msg is None:
            # the producer emits None to indicate that it is done
            break
        # process the msg
        if msg.msg_id == 4:
            raise Exception('an exception happened!')

        print('consumed {}...'.format(msg))
        # simulate i/o operation using sleep
        await asyncio.sleep(random.random())


if __name__ == '__main__':
    queue = asyncio.Queue()
    producer_coro = produce(queue, 5)
    consumer_coro = consume(queue)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(producer_coro)
    loop.run_until_complete(consumer_coro)
    loop.close()
