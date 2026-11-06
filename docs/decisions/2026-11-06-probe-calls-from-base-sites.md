# A probe call takes its arguments from the base code

## What changed

Before a model-written probe is saved, each call it makes on a function or class in the base
tree is compared with that definition. The definition is the class or function itself. An import
that only re-exports the name is followed to that definition.

The comparison looks at three things. A keyword has to be one of the parameters. A parameter
with no default has to be given. A call cannot pass more positional arguments than the
definition accepts, unless the definition has `*args`. A definition that accepts `**kwargs` is
left alone, because any name is allowed. A class that does not write its own `__init__` is not
counted this way, because a decorator may have added the constructor.

When a call does not match, arguments the definition accepts stay, including the values the
probe wrote. An unexpected keyword is not deleted: removing it would leave a different call, so
the probe is not run, and the reason names the keyword. A required parameter that is still
missing is filled from a base call that passes that same parameter, and the record names the
file and the parameter. The rest of that call is not copied. A call we cannot check, because it
uses `*args` or `**kwargs` or because the constructor or method is inherited from another file,
is not run either. A matching signature is not by itself proof that the changed line ran.

Those calls are read from the base files, tests and source, as syntax only. The walk stops
after a fixed number of files. It does not import the package and it does not use the network.
A name used as an argument is copied only when the same function assigned it a value that can
be copied (a constant, or another such call). A subscript such as `names[0]` in the
implementation is not a call and is not used as an argument. An import that only says
`from module import *` is followed one step when that module defines the name, so a test that
imports the class through the package is still a real call.

A required parameter that no base call shows is not filled with a guess. A call whose every
argument was invalid is not rewritten into the default call. The probe is then not written
and not run, and the reason names a base call that was deliberately not copied when one was
found.

The model's choice of which function to call is kept. Only the arguments change. A call that
already matches the signature is not rewritten, so a later answer that is already valid is kept
even when its values differ from the base call.

The one repair the generator already makes is the place this is explained. That prompt now
includes the parameter list and a few real calls from the base files. There is no extra model
call. If that answer is still unsound, the arguments are bound as above, or the probe is dropped.

Which tests pytest collects is unchanged. A new test is still run on the base only when the
existing changed-test rule selects its file. Reading a call out of a base file does not mean
that test was executed.

## Why

A generated probe called a constructor with a keyword the base definition does not have. The
same `TypeError` then happened on both sides. The call never reached the change. The keyword
was copied from the pull-request wording, not from a call the project already makes. Checking
that the name exists was not enough: the name was real, and the arguments were not.

A matching exception on both sides is still not evidence. A probe that does run and sees a
real difference is still judged as before.

## Decision

Bind the arguments before the probe is frozen, from the base tree only. Freeze still happens
before any pull-request-side run, and the bound file is what gets frozen. If the arguments
cannot be bound, do not run the probe. Marking it not run drops its observations and sets its
covered-line count to 0, so it cannot prove a claim and it does not by itself need attention.
A different probe that sees a real difference still does.

The pull-request tree is not a source of arguments. A call that appears only there is not
copied onto the base.

## Alternatives and tradeoffs

Asking the model again, with no extra call, still leaves it free to invent a keyword. The
binding step does not trust that second answer when the call still does not match.

Inventing `None` for a missing required argument would run, and then fail inside the function
for a reason that has nothing to do with the change. Leaving the probe unrun is the honest
result. The project's own tests remain the evidence when they already ran under the existing
rules. This change does not add a test to the base run and does not treat a new test as having
run on the base unless that existing rule already selected it.

Copying only calls whose values are constants or other copied calls misses a call that passes
a fixture parameter. That probe is not run. Guessing the fixture's value would be the same
invention this change refuses.

## What it means for you

A probe that invents a parameter keeps the arguments that were already valid. A missing required
parameter is filled from a base call of that same parameter when one can be copied. A call with
nothing valid left is not replaced by another call of the same name, and it is not run. A
dropped probe covers no changed line. A probe that already calls the function correctly is
unchanged. Offline tests do not re-run a live check. A live run of the pull request that showed
this failure still has to be done with the real model after this is merged.
