# -*- coding: utf-8 -*-
"""
Created on Sun May  8 08:15:46 2022

@author: simon
"""
import json
import rsa
from colorama import Fore, Back, Style

class Encryption_Handler:    
    global private_key
    global public_keys
    
    private_key = None
    public_keys = {}
    
    def get_keys(self, component_name, config):
        global private_key
        global public_keys
        
        with open("generated_keys.json", "r") as f:
            all_keys = json.load(f)
            
            for key in all_keys:
                if key == component_name:
                    private_key = rsa.PrivateKey.load_pkcs1(all_keys[key][1].encode("utf8"))
                
                public_keys[key] = rsa.PublicKey.load_pkcs1(all_keys[key][0].encode("utf8"))
               
            
            
            
    def encrypt(self, dest_name, data):
        if private_key:
            for role in public_keys:
                if role == dest_name:
                    try:
                        encrypted_data = bytearray()
                        
                        for n in range(0,len(data), 245):
                            part = data[n:n+245]
                            encrypted_data += rsa.encrypt(part, public_keys[role])
                            
                        return bytes(encrypted_data)
                    except:    
                        print(Back.RED, "Was not able to encrypt data", Style.RESET_ALL)
                        
            print(Back.RED, "ERROR: Could not find correct public key. ~encryption_handler", Style.RESET_ALL)
        else:
            print(Back.RED, "ERROR: Keys not loaded correctly. ~encryption_handler", Style.RESET_ALL)
        return data
        
    
    
    
    
    
    def decrypt(self, data):
        global private_key
        
        if private_key:                
            decrypted_data = bytearray()
                
            for n in range(0,len(data), 256):
                part = data[n:n+256]
                
                try:
                    decrypted_data += rsa.decrypt(part, private_key)
                except:
                    print(Back.RED, "DATA NOT DECRYPTABLE", Style.RESET_ALL)
                    return None
            
            return bytes(decrypted_data)
        
        else:
            print(Back.RED, "ERROR: Keys not loaded correctly. ~encryption_handler", Style.RESET_ALL)
        
        return data
    