from enum import Enum


class Direction(Enum):
    READ = 'READ'
    WRITE = 'WRITE'


class Command:
    def __call__(self, bus, addr):
        if self.direction == Direction.READ:
            data = bus.read_word_data(addr, self.code)
            return Command(code=self.code,
                           payload=data,
                           direction=Direction.READ)
        else:
            bus.write_word_data(addr, self.code, self.payload)

    def __init__(self, code=None, payload=None, direction=None):
        self.code = code
        self.payload = payload
        self.direction = direction
