#!/usr/bin/env python3

import random, logging
from bspl.adapter import Adapter
from bspl.adapter.core import COLORS
from configuration import config

# logging.getLogger("bungie").setLevel(logging.DEBUG)

import Purchase
from Purchase import Seller, quote, ship

adapter = Adapter(Seller, Purchase.protocol, config, color=COLORS[1])


@adapter.enabled(quote)
async def send_quote(msg):
    msg["price"] = random.randint(0, 100)
    return msg


@adapter.enabled(ship)
async def send_ship(msg):
    msg["shipped"] = True
    return msg


if __name__ == "__main__":
    adapter.start()
