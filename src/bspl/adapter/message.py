#!/usr/bin/env python3

from agentspeak import Literal
import re
from fastcore.foundation import camel2snake


def get_key(schema, payload):
    # schema.keys should be ordered, or sorted for consistency
    return ",".join(k + ":" + str(payload[k]) for k in schema.keys)


class Message:
    schema = None
    payload = {}
    acknowledged = False
    dest = None
    adapter = None
    meta = {}
    key = None
    signed_payload={}

    def __init__(self, schema, payload, signed_payload={}, acknowledged=False, dest=None, adapter=None):
        self.schema = schema
        self.payload = payload
        self.acknowledged = acknowledged
        self.dest = dest
        self.adapter = adapter
        self.meta = {}
        self.signed_payload = signed_payload

    @property
    def key(self):
        return get_key(self.schema, self.payload)

    def __repr__(self):
        stripped_payload = {}#Payload with stripped signatures to improve visualization
        signatures = []
        
        for parameter in self.payload:
            if parameter.endswith("_signed"):
                signatures.append(parameter)
            else:
                stripped_payload[parameter] = self.payload[parameter]
                
        stripped_payload["signatures"] = signatures
        payload = ",".join("{0}={1!r}".format(k, v) for k, v in stripped_payload.items())
        return f"{self.schema.name}({payload})"

    def __eq__(self, other):
        return self.payload == other.payload and self.schema == other.schema

    def __hash__(self):
        return hash(self.schema.qualified_name + self.key)

    def __getitem__(self, name):
        return self.payload[name]

    def __setitem__(self, name, value):
        if name not in self.schema.parameters:
            raise Exception(f"Parameter {name} is not in schema {self.schema}")
        adornment = self.schema.parameters[name].adornment
        if adornment == "out":
            self.payload[name] = value
            return value
        else:
            raise Exception(f"Parameter {name} is {adornment}, not out")

    def bind(self, **kwargs):
        for k, v in kwargs.items():
            self[k] = v
        return self

    def instance(self, **kwargs):
        """
        Return new instance of message, binding new parameters from kwargs
        """
        return self.schema(**self.payload).bind(**kwargs)

    def keys_match(self, other):
        return all(
            self.payload[k] == other.payload[k]
            for k in self.schema.keys
            if k in other.schema.parameters
        )

    def keys(self):
        return self.payload.keys()

    def project_key(self, schema):
        """Give the subset of this instance's keys that match the provided schema, in the order of the provided schema"""
        key = []
        # use ordering from other schema
        for k in schema.keys:
            if k in self.schema.keys:
                key.append(k)
        return ",".join(k + ":" + str(self.payload[k]) for k in key)

    def send(self):
        self.adapter.send(self)
