class Parser:
    def __init__(self, contexts=(), initial=None, ignore_unknown=False):
        self.contexts = list(contexts)
        self.initial = initial
        self.ignore_unknown = ignore_unknown
