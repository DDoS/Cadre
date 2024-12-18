from typing import Protocol

import numpy
import numpy.typing

class Display(Protocol):
    buf: numpy.typing.NDArray[numpy.uint8]

    # Optional attributes:
    #   palette: py_encre.Palette
    #   output_rotation: py_encre.Rotation
    #   info: dict[str, Any]

    def show(self):
        ...
