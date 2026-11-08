"""Room capacity model."""
from dataclasses import dataclass

@dataclass
class Room:
    id: int
    capacity: int
    occupied: int

    def can_allocate(self):
        return self.occupied < self.capacity
