from display_protocol import Display

def init_display() -> Display:
    from inky.auto import auto
    return auto()
