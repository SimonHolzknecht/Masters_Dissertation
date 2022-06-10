from configuration import config
from bspl.security import key_generator

#Simple script to generate required key paris and store it into a local json file
key_generator.config_setup(config)
key_generator.generate_keys()
key_generator.store_keys()