import json
import rsa
from colorama import Fore, Back, Style
import traceback


#This class deals with the signing and verifying of parameters. Parameters are 
#signed in combination with their protocol "keys" taken from the BSPL protocol 
#passed on initiation.
class Signature_Handler:
    
    def __init__(self, role_name, protocol):
        self.private_key = None
        self.public_keys = {}
        
        self.role_name = role_name
        self.protocol = protocol
        self.parameter_origins = protocol.parameter_origins#dict to map parameters to their origin entity        
        #self.bind_paramters_to_origin(protocol)
        #self.determine_origin(protocol)
        self.parameter_keys = {} #dict to map parameters to their BSPL enactment keys
        self.bind_parameters_to_keys(protocol.to_dict())
        self.forwarded_parameters = [] #list to capture parameters that are forwarded by this entity
        self.determine_forwarded_parameters(protocol.to_dict())
        
        self.previous_signatures = {}
        
        
        #Retrieve and save local keys saved in "generated_keys.json"
        with open("generated_keys.json", "r") as f:
            all_keys = json.load(f)
            
            for key in all_keys:
                if key == role_name:
                    self.private_key = rsa.PrivateKey.load_pkcs1(all_keys[key][1].encode("utf8"))
                
                self.public_keys[key] = rsa.PublicKey.load_pkcs1(all_keys[key][0].encode("utf8"))
                
    
    #Function to map parameters to the keys they are connected to on creation 
    #according to the protocol
    def bind_parameters_to_keys(self, protocol):        
        for message in protocol["messages"]:
            for parameter in protocol["messages"][message]["outs"]:
                self.parameter_keys[parameter] = protocol["messages"][message]["keys"]
    
    
    
    #Function to extract parameters forwarded by this entity. This is done to prevent storage
    #of redundant signatures.
    def determine_forwarded_parameters(self, protocol):
        for message in protocol["messages"]:
            if protocol["messages"][message]["from"] == self.role_name:
                for parameter in protocol["messages"][message]["parameters"]:
                    self.forwarded_parameters.append(parameter)
        
        
        
        
        
    
        
    #Methos that checks all parameters in a message and uses included signtatures
    def verify_parameters(self, message):
        try:
            for parameter in message.payload:
                if parameter.find("_signed") == -1:#If not a signature
                    parameter_keys = [message.payload[p] for p in self.parameter_keys[parameter]]
                    
                    result = self.verify(message.payload[parameter], ";".join(str(entry) for entry in parameter_keys), message.payload[parameter+"_signed"], self.parameter_origins[(message.schema.name, parameter)])
                    if result is False:
                        print(Back.RED, "Could not verify message ",message, Style.RESET_ALL)
                        return False
        except Exception:
            print(Back.RED, "Could not verify message ",message, Style.RESET_ALL)
            traceback.print_exc()
            return False
                
        return True
        
    
    
    #Method to verify a single parameter
    def sign(self, parameter_name, payload):       
        parameter_keys = [payload[p] for p in self.parameter_keys[parameter_name]]
        
        signature = rsa.sign((str(payload[parameter_name]) + ";".join(str(entry) for entry in parameter_keys)).encode(), self.private_key, "SHA-1")
        
        return signature.decode("ISO-8859-1")
    
    
    
    
    #Method to verify a single parameter. "parameter_keys" refers to the parameters
    #adorned "key" in the BSPL protocol
    def verify(self, parameter, parameter_keys, signature, origin_name):
        try:
            rsa.verify((str(parameter) + parameter_keys).encode(), signature.encode("ISO-8859-1"), self.public_keys[origin_name])
            
            return True
        except Exception:
            print(Back.RED, "Could not verify parameter {}.".format(parameter), Style.RESET_ALL)
            traceback.print_exc()
            
            return False
        