class Argument:
    def __init__(self, name, positional=False):
        self.name = name
        self.names = (name,)
        self.positional = positional
