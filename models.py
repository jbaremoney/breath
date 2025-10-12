import time
from enum import Enum

class BlowState(Enum):
    CACHED_NAME = "cached_name"
    PREBLOW = "preblow"
    BLOWING = "blowing"
    FINISHED = "finished"

class BlowSession():
    # initialize a BlowSession when the name is successfully cached
    def __init__(self, name):
        self.name = name
        self.ts = time.time()
        self.state = BlowState.CACHED_NAME
        self.bac = None # currently just a voltage while calibrating

    def update_state(self, new_state: BlowState):
        self.state = new_state

    def set_bac(self, bac: float):
        """
        setting the bac of the session. also updates state to finished
        """
        self.bac = bac
        self.update_state(BlowState.FINISHED)
