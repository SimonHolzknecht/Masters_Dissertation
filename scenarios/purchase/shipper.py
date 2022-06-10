#!/usr/bin/env python3

import random
from bspl.adapter import Adapter
from configuration import config

import Purchase
from Purchase import Shipper, deliver

adapter = Adapter(Shipper, Purchase.protocol, config)


@adapter.enabled(deliver)
async def deliver_item(msg):
    msg["outcome"] = "delivered"
    return msg


if __name__ == "__main__":
    adapter.start()
