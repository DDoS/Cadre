from display_protocol import Display

def init_display(_) -> Display:
    from inky.auto import auto
    return auto()
