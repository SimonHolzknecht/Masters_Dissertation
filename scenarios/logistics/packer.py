import logging
from bspl.adapter import Adapter, Remind
from bspl.adapter.statistics import stats_logger
from configuration import config, logistics
#import bspl.security.key_handler as key_handler

from Logistics import Packer, Packed

adapter = Adapter(Packer, logistics, config)

logger = logging.getLogger("bungie")
# logger.setLevel(logging.DEBUG)



@adapter.enabled(Packed)
async def pack(msg):
    msg["status"] = "packed"
    return msg


if __name__ == "__main__":
    logger.info("Starting Packer...")
    adapter.start()
