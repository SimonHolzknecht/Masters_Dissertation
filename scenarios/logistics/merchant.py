from bspl.adapter import Adapter, Remind
from bspl.adapter.statistics import stats_logger
from configuration import config
import random
import time
import datetime
import asyncio
import logging
#import time

import Logistics
from Logistics import Merchant, RequestLabel, RequestWrapping, Packed


adapter = Adapter(Merchant, Logistics.protocol, config)
logger = logging.getLogger("merchant")
# logging.getLogger('bungie').setLevel(logging.DEBUG)

stats = {"init_keys": set(), "finished_keys": set(), "information": [0], "done": False}

#global start_time

async def order_generator():
    for orderID in range(10):
        await adapter.send(
            RequestLabel(
                orderID=orderID,
                address=random.sample(["Lancaster University", "NCSU"], 1)[0],
            )
        )
        for i in range(2):
            await adapter.send(
                RequestWrapping(
                    orderID=orderID,
                    itemID=i,
                    item=random.sample(["ball", "bat", "plate", "glass"], 1)[0],
                )
            )
        await asyncio.sleep(0)
    stats["done"] = True


@adapter.reaction(RequestWrapping)
async def requested(message):
    stats["init_keys"].add(message.key)


@adapter.reaction(Packed)
async def packed(message):
    stats["finished_keys"].add(message.key)
    print(message)
    
    #global start_time
    #print("Time elapsed on reception: ", (time.time() - start_time))

async def status_logger():
    start = datetime.datetime.now()
    while True:
        initiated = len(stats["init_keys"])
        completed = len(stats["finished_keys"])
        if not stats["done"]:
            duration = datetime.datetime.now() - start
            rate = completed / duration.total_seconds()
        logger.info(
            f"initiated: {initiated}, completed: {completed}, duration: {duration}, rate: {rate}"
        )
        logger.info(f"TX: {adapter.emitter.stats}")
        await asyncio.sleep(3)


if __name__ == "__main__":
    print("Starting Merchant...")
    
    #global start_time
    #start_time = time.time()

    
    adapter.start(order_generator(), stats_logger(3), status_logger())
