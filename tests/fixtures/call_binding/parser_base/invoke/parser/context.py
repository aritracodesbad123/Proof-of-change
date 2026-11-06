class ParserContext:
    def __init__(self, name=None, aliases=(), args=()):
        self.name = name
        self.aliases = tuple(aliases)
        self.args = args
