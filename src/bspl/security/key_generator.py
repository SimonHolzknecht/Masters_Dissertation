# -*- coding: utf-8 -*-
"""
Created on Wed May  4 19:26:53 2022

@author: simon
"""

import rsa
import json

            
            
#store keys from dict in local JSON file
def store_keys():
    with open("generated_keys.json", "w") as f:
        json.dump(component_keys, f, indent=2)
            
            
            

#Generate and return asymmetric keys per system component
def generate_keys():
    generated_key_count = 1
    
    print("Initiating generation of ", len(component_keys), " key pairs...")
    
    for key in component_keys:

        #public_key = private_key.public_key()
        #start_time = datetime.now()
        
        #print("pos1 - ", datetime.now() - start_time)
        
        public_key, private_key = rsa.newkeys(2048) 
        
        
        #print("pos2 - ", datetime.now() - start_time)
        publicKeyPkcs1PEM = public_key.save_pkcs1().decode('utf8')
        #print("pos3 - ", datetime.now() - start_time)
        privateKeyPkcs1PEM = private_key.save_pkcs1().decode('utf8')
        
        
        #print("pos4 - ", datetime.now() - start_time)
        component_keys[key] = (publicKeyPkcs1PEM, privateKeyPkcs1PEM)
        
        print("Key pair ", generated_key_count, " of ", len(component_keys), " generated...")
        generated_key_count += 1
        
        #print(key, "_public=\n", publicKeyPkcs1PEM)
        #print(key, "_private=\n", privateKeyPkcs1PEM)


def config_setup(config):    
    global component_keys
    component_keys = {}
    
    for key in config:
        component_keys[key.name] = ("","")