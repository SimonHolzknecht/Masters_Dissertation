# -*- coding: utf-8 -*-
"""
Created on Wed May  5 12:39:43 2022

@author: simon
"""
import json

private_key = None
public_keys = {}




def get_keys(component_name):
    with open("generated_keys.json", "r") as f:
        all_keys = json.load(f)
        
        for key in all_keys:
            if key == component_name:
                private_key = all_keys[key][1]
            
            public_keys[key] = all_keys[key][0]
            
        print(component_name, "_private= ", private_key)
        print("\nall_public=\n", public_keys)
    