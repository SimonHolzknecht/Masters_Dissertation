import asyncio
import aiorun
import logging
import json
import datetime
import sys
import os
import math
import socket
import inspect
import yaml
import random
import colorama
from types import MethodType
from asyncio.queues import Queue
from .store import Store
from .message import Message
from functools import partial
from .emitter import Emitter
from .receiver import Receiver
from .scheduler import Scheduler, exponential
from .statistics import stats, increment
from . import policies
from .encryption_handler import Encryption_Handler
from .signature_handler import Signature_Handler
from colorama import Fore, Back, Style

FORMAT = "%(asctime)-15s %(module)s: %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger("bspl")

logging.getLogger("aiorun").setLevel(logging.CRITICAL)

COLORS = [
    (colorama.Back.GREEN, colorama.Fore.WHITE),
    (colorama.Back.MAGENTA, colorama.Fore.WHITE),
    (colorama.Back.YELLOW, colorama.Fore.BLACK),
    (colorama.Back.BLUE, colorama.Fore.WHITE),
    (colorama.Back.CYAN, colorama.Fore.BLACK),
    (colorama.Back.RED, colorama.Fore.WHITE),
]


class ObservationEvent:
    type = None
    pass


class ReceptionEvent(ObservationEvent):
    def __init__(self, message):
        self.type = "reception"
        self.messages = [message]


class EmissionEvent(ObservationEvent):
    def __init__(self, messages):
        self.type = "emission"
        self.messages = messages


def instantiate(adapter):
    def inner(schema, *args, **kwargs):
        payload = {}
        for i, p in enumerate(schema.parameters.values()):
            if i < len(args):
                payload[p] = args[i]

        # Ensure keys are declared
        for k in schema.keys:
            payload[k] = None

        for k in kwargs:
            if k in schema.parameters:
                payload[k] = kwargs[k]
            # else:
            #     logger.error(f'Parameter not in schema: {k}')
            #     return None
        
        return Message(schema, payload, adapter=adapter)

    return inner


class Adapter:
    def __init__(
        self,
        role,
        protocol,
        configuration,
        emitter=Emitter(),
        receiver=None,
        color=None,
        encryption_handler = Encryption_Handler()
    ):
        """
        Initialize the agent adapter.

        role: name of the role being implemented
        protocol: a protocol specification
          {name, keys, messages: [{name, from, to, parameters, keys, ins, outs, nils}]}
        configuration: a dictionary of roles to endpoint URLs
          {role: url}
        """        
        
        self.logger = logging.getLogger("bspl.adapter")
        
        #GIVE ENCRYPTION HANDLER TO EMITTER
        encryption_handler.get_keys(role.name, configuration)
        self.encryption_handler = encryption_handler
        emitter.encryption_handler = encryption_handler
        
        #INITIATE SIGNATURE HANDLER
        self.signature_handler = Signature_Handler(role.name, protocol)
        
        self.logger.propagate = False
        color = color or COLORS[int(role.name, 36) % len(COLORS)]
        self.color = color
        reset = colorama.Fore.RESET + colorama.Back.RESET
        formatter = logging.Formatter(
            f"%(asctime)-15s ({''.join(self.color)}%(role)s{reset}) %(module)s: %(message)s"
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.role = role
        self.protocol = protocol
        self.configuration = configuration
        self.reactors = {}  # dict of message -> [handlers]
        self.generators = {}  # dict of (scheema tuples) -> [handlers]
        self.history = Store()
        self.emitter = emitter
        self.receiver = receiver or Receiver(configuration[role])
        #GIVE KEY HANDLER TO RECEIVER
        self.receiver.encryption_handler = self.encryption_handler
        self.schedulers = []
        self.projection = protocol.projection(role)

        self.inject(protocol)

        self.enabled_messages = Store()
        self.decision_handler = None
        
        
        """
        This dict holds received signatures. Signatures are saved to this dict 
        with the dict key being "(parameter_name, parameter_key_values*)". 
        "parameter_key_values" refers to the key values correlated to received 
        parameters according to the "parameter_keys" dict.
        """
        self.previous_signatures = {}

    def debug(self, msg):
        self.logger.debug(msg, extra={"role": self.role.name})

    def info(self, msg):
        self.logger.info(msg, extra={"role": self.role.name})

    def warn(self, msg):
        self.logger.warn(msg, extra={"role": self.role.name})

    def inject(self, protocol):
        """Install helper methods into schema objects"""

        from ..protocol import Message

        # this means we can only have one adapter per agent...
        Message.__call__ = instantiate(self)

        for m in protocol.messages.values():
            m.adapter = self

    async def receive(self, payload):
        self.debug(f"Received payload: {payload}")
        if not isinstance(payload, dict):
            self.warn("Payload does not parse to a dictionary: {}".format(payload))
            return

        schema = self.protocol.find_schema(payload, to=self.role)
        self.debug(f"Found schema: {schema}")
        if not schema:
            self.warn("No schema matching payload: {}".format(payload))
            return
        
        #Check if correct signed value names are present
        signed_parameters = [p for p in payload if p.endswith("_signed")]
        
        for signed_parameter in signed_parameters:
            if not signed_parameter.replace("_signed", "") in payload:
                self.warn("No schema matching payload: {}".format(payload))
                return
        
        message = Message(schema, payload)
        message.meta["received"] = datetime.datetime.now()
                
        
        
        
        #Verify parameters using their signatures
        if self.signature_handler.verify_parameters(message) is False:
            self.warn("Signatures invalid for received message: {}".format(message))
            print(Back.RED, "Verification failed for message ", message, Style.RESET_ALL)
            return
        
        #Save signatures for potential future use
        for parameter in message.schema.to_dict()["parameters"]:
            if parameter in self.signature_handler.forwarded_parameters and (parameter+"_signed") in message.payload:
                dict_key = (self.protocol.parameter_origins[(message.schema.name,parameter)], parameter,) + tuple([message.payload[p] for p in self.signature_handler.parameter_keys[parameter]])
                
                self.previous_signatures[dict_key] = message.payload[parameter+"_signed"]
                
           
        
        
        increment("receptions")
        if self.history.is_duplicate(message):
            self.debug("Duplicate message: {}".format(message))
            increment("dups")
            # Don't react to duplicate messages
            # message.duplicate = True
            # await self.react(message)
        elif self.history.check_integrity(message):
            self.debug("Observing message: {}".format(message))
            increment("observations")
            self.history.add(message)
            await self.signal(ReceptionEvent(message))

    async def send(self, *messages):
        for message in messages:
            #Check for redundant signatures where the parameter is missing
            removable_keys = [p for p in message.payload if (p.find("_signed") != -1) 
                              and (p.replace("_signed", "") not in message.payload)]
            
            for removable in removable_keys:
                print(Back.Yellow, "Removed signature ", removable, " from message due to missing parameter.", Style.RESET_ALL)
                del message.payload[removable]
            
            
            
            #Signing "out"-adorned parameters
            for out_parameter in message.schema.to_dict()["outs"]:
                dict_key = (self.role.name, out_parameter,) + tuple([message.payload[p] for p in self.signature_handler.parameter_keys[out_parameter]])
                
                if dict_key in self.previous_signatures:
                    message.payload[out_parameter + "_signed"] = self.previous_signatures[dict_key]
                else:
                    self.previous_signatures[dict_key] = self.signature_handler.sign(out_parameter, message.payload)
                    message.payload[out_parameter + "_signed"] = self.previous_signatures[dict_key]
            
            
            #Check if all parameters have signatures
            for parameter in message.schema.to_dict()["parameters"]:
                if (parameter + "_signed") not in message.payload:
                    dict_key = (self.protocol.parameter_origins[(message.schema.name,parameter)], parameter,) + tuple([message.payload[p] for p in self.signature_handler.parameter_keys[parameter]])
                    if dict_key in self.previous_signatures:
                        message.payload[parameter + "_signed"] = self.previous_signatures[dict_key]
                    else:
                        print(Back.RED, "Signature missing for '{}' and was not able to retrieve it from previous signatures.".format(parameter), Style.RESET_ALL)
        
        
        
        def prep(message):
            if not message.dest:
                message.dest = self.configuration[message.schema.recipient]
            return message

        emissions = set(prep(m) for m in messages if not self.history.is_duplicate(m))
        if len(emissions) < len(messages):
            self.info(
                f"({self.role.name}) Skipped duplicate messages: {set(messages).difference(emissions)}"
            )

        if self.history.check_emissions(emissions):
            for m in emissions:
                self.history.add(m)
            if hasattr(self.emitter, "bulk_send"):
                self.debug(f"bulk sending {len(emissions)} messages")
                await self.emitter.bulk_send(emissions)
            else:
                for m in emissions:
                    await self.emitter.send(m)
            await self.signal(EmissionEvent(emissions))
            

    def register_reactor(self, schema, handler, index=None):
        if schema in self.reactors:
            rs = self.reactors[schema]
            if handler not in rs:
                rs.insert(index if index is not None else len(rs), handler)
        else:
            self.reactors[schema] = [handler]

    def register_reactors(self, handler, schemas=[]):
        for s in schemas:
            self.register_reactor(s, handler)

    def reaction(self, *schemas):
        """
        Decorator for declaring reactor handler.

        Example:
        @adapter.reaction(MessageSchema)
        async def handle_message(message):
            'do stuff'
        """
        return partial(self.register_reactors, schemas=schemas)

    async def react(self, message):
        """
        Handle emission/reception of message by invoking corresponding reactors.
        """
        reactors = self.reactors.get(message.schema)
        if reactors:
            for r in reactors:
                self.debug("Invoking reactor: {}".format(r))
                message.adapter = self
                await r(message)

    def enabled(self, *schemas, **options):
        """
        Decorator for declaring enabled message generators.

        Example:
        @adapter.enabled(MessageSchema)
        async def generate_message(msg):
            msg.bind("param", value)
            return msg
        """
        return partial(self.register_generators, schemas=schemas, options=options)

    def register_generators(self, handler, schemas, options={}):
        if schemas in self.generators:
            gs = self.generators[schemas]
            if handler not in gs:
                gs.insert(index if index is not None else len(gs), handler)
        else:
            self.generators[schemas] = [handler]

    async def handle_enabled(self, message):
        """
        Handle newly observed message by checking for newly enabled messages.

        1. Cycle through all registered schema tuples
        2. Check if all messages in tuple are enabled
        3. If so, invoke the handlers in sequence
        4. Continue until a message is returned
        5. Break loop after the first handler returns a message, and send it

        Note: sending a message triggers the loop again
        """
        for tup in self.generators.keys():
            for group in zip(*(schema.match(**message.payload) for schema in tup)):
                for handler in self.generators[tup]:
                    # assume it returns only one message for now
                    msg = await handler(*group)
                    if msg:
                        await self.send(msg)
                        # short circuit on first message to send
                        return

    async def task(self):
        loop = asyncio.get_running_loop()

        loop.create_task(self.update_loop())

        await self.receiver.task(self)

        if hasattr(self.emitter, "task"):
            await self.emitter.task()
        for s in self.schedulers:
            # todo: add stop event support
            loop.create_task(s.task(self))

    def add_policies(self, *ps, when="reactive"):
        for policy in ps:
            # action = policy.get('action')
            # if type(action) is str:
            #     action = policies.parse(self.protocol, action)
            for schema, reactor in policy.reactors.items():
                self.register_reactor(schema, reactor, policy.priority)
            if when != "reactive":
                s = Scheduler(when)
                self.schedulers.append(s)
                s.add(policy)

    def load_policies(self, spec):
        if type(spec) is str:
            spec = yaml.full_load(spec)
        if self.role.name in spec:
            for condition, ps in spec[self.role.name].items():
                self.add_policies(*ps, when=condition)
        else:
            # Assume the file contains policies only for agent
            for condition, ps in spec.items():
                self.add_policies(*ps, when=condition)

    def load_policy_file(self, path):
        with open(path) as file:
            spec = yaml.full_load(file)
            self.load_policies(spec)

    def start(self, *tasks, use_uvloop=True):
        async def main():
            await self.task()
            loop = asyncio.get_running_loop()
            for t in tasks:
                loop.create_task(t)

        self.running = True
        aiorun.run(main(), stop_on_unhandled_errors=True, use_uvloop=use_uvloop)

    async def stop(self):
        await self.receiver.stop()
        await self.emitter.stop()
        self.running = False

    async def signal(self, event):
        """
        Publish an event for triggering the update loop
        """
        await self.events.put(event)

    async def update_loop(self):
        self.events = Queue()

        while self.running:
            event = await self.events.get()
            self.debug(f"event: {event}")
            emissions = await self.process(event)
            if emissions:
                if self.history.check_emissions(emissions):
                    await self.send(*emissions)

    async def process(self, event):
        """
        Process a single functional step in a decision loop

        (state, observations) -> (state, enabled, event) -> (state, emissions) -> state
        - state :: the local state, history of observed messages + other local information
        - event :: an object representing the new information that triggered the processing loop; could be an observed message or a signal from the agent internals or environment
        - enabled :: a set of all currently enabled messages, indexed by their keys; the enabled set is incrementally constructed and stored in the state
        - emissions :: a list of message instance for sending

        State can be threaded through the entire loop to make it more purely functional, or left implicit (e.g. a property of the adapter) for simplicity
        Events need a specific structure;
        """

        if isinstance(event, ObservationEvent):
            # Update the enabled messages if there was an emission or reception
            observations = event.messages
            event = self.compute_enabled(observations)
            for m in observations:
                self.debug(f"observing: {m}")
                await self.react(m)
                await self.handle_enabled(m)

        if self.decision_handler:
            return await self.decision_handler(self.enabled_messages, event)

    def compute_enabled(self, observations):
        """
        Compute updates to the enabled set based on a list of an observations
        """

        # clear out matching keys from enabled set
        removed = set()
        for msg in observations:
            context = self.enabled_messages.context(msg)
            removed.update(context.messages)
            context.clear()

        added = set()
        for o in observations:
            for schema in self.projection.messages.values():
                added.update(schema.match(**o.payload))
        for m in added:
            self.debug(f"new enabled message: {m}")
            self.enabled_messages.add(m)
        removed.difference_update(added)

        return {"added": added, "removed": removed, "observations": observations}
