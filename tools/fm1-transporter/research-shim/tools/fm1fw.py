"""Stand-in for fm-1-research-lab's Firmware: the V15 package's raw flash
image is its type-0 entry, 0x93000 bytes at file offset 0x414."""
class Firmware:
    def __init__(self, raw):
        self.raw, self.skew, self.product = raw, 0, "FM-1_015 (stock V15)"
        self.entries = [{"type": 0, "data_off": 0x414, "size": 0x93000}]
