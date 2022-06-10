import bspl

logistics = bspl.load_file("purchase.bspl").export("Purchase")
from Purchase import Buyer, Seller, Shipper

config = {
    Buyer: ("0.0.0.0", 8000),
    Seller: ("0.0.0.0", 8001),
    Shipper: ("0.0.0.0", 8002),
}
