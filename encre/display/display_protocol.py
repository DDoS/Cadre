from typing import Protocol

import numpy
import numpy.typing

class Display(Protocol):
    buf: numpy.typing.NDArray[numpy.uint8]

    def show(self):
        ...
