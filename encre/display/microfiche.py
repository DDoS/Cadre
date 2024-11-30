import tempfile
from typing import Any
from pathlib import Path

import numpy
import numpy.typing

import requests

from display_protocol import Display

import py_encre

class Microfiche:
    palette: py_encre.Palette
    output_rotation: py_encre.Rotation

    def __init__(self, config: dict[str, Any]):
        size = (config['height'], config['width'])
        self.buf = numpy.zeros(size, numpy.uint8)
        self._url = config.get('url')

    def show(self):
        with tempfile.TemporaryDirectory() as dir_name:
            file_path = dir_name / Path('encre.bin')
            py_encre.write_encre_file(self.buf, self.palette.points, self.output_rotation, str(file_path))
            requests.post(self._url, data=open(file_path, 'rb')).raise_for_status()


def init_display(config: dict[str, Any]) -> Display:
    return Microfiche(config)
