from invoke.parser import Argument, Context, Parser


class Parser_:
    class positional_arguments:
        def _basic(self):
            arg = Argument("pos", positional=True)
            mytask = Context(name="mytask", args=[arg])
            return Parser(contexts=[mytask])

        def omitted_positional_arg_raises_ParseError(self):
            self._basic().parse_argv(["mytask"])

        def takes_ignore_unknown_kwarg(self):
            Parser(ignore_unknown=True)

        def ignore_unknown_defaults_to_False(self):
            assert Parser().ignore_unknown is False
