# A probe may call a function that accepts extra arguments

## What changed

Before a model-written probe is saved, each call it makes on a function or class in the base
tree is compared with that definition. The definition is read from the file. Nothing is imported
and nothing is executed for this comparison.

A definition that accepts `**kwargs` used to make the whole probe be dropped. The named
parameters were thrown away, so a keyword that really is a parameter was treated the same as a
keyword that is not. The same thing happened for a call written with `*args` when the definition
accepts `*args`.

Named parameters are checked again. A keyword the definition lists has to be one of those names,
including when `**kwargs` is also there. A keyword that is not listed is allowed only when
`**kwargs` is there, because that is where it goes. An extra positional argument is allowed only
when `*args` is there. A required parameter is still required. A positional-only parameter still
cannot be passed by name. A keyword that is not a parameter is still rejected when the definition
has no `**kwargs`.

A call written as `**mapping` is still not judged. The names inside the mapping are not visible,
so the probe is not run.

A class that does not write its own `__init__` is followed to the base class, including a base
class in another file of the same tree. When that constructor can be read, the call is checked
against it. `typing.overload` stubs are skipped and the real `__init__` is used.

A dataclass, an attrs class, or a `NamedTuple` whose fields can be read is checked against those
fields. When a field or a base class cannot be read, the call is not judged and the probe is
still run. A method or constructor whose parameters are not in a file we can read is treated the
same way: the probe runs. A wrong keyword then raises on both sides. A matching exception on both
sides is still not evidence.

## Why

Real probes were dropped only because the target accepts `**kwargs` or was called with `*args`.
On 19 November 2026 that was 15 probes across 6 of 8 stored records. The calls were aiming at
constructors and functions that do take those arguments: a table, a task collection, a config
object, a URL, a file sink, `compose`, a spooled buffer, a connection error, and a header
dictionary. The rule is the same for every library. There is no list of allowed libraries.

A keyword that is not a parameter, on a definition that has no `**kwargs`, still never reaches
the changed line. Dropping that probe is unchanged.

## Decision

Check the names the definition declares. Let extra arguments flow into `*args` and `**kwargs`,
and run the probe. Do not judge a call written as `**mapping`. Do not invent a parameter, and do
not delete an argument to make a different call run. When the parameters cannot be read, run the
probe instead of dropping it. Do not treat a later exception that is the same on both sides as
evidence. Do not re-judge a stored record into `verified` from this rule: a dropped probe has no
saved observations, and this change does not create any.

## Alternatives and tradeoffs

Leaving every `**kwargs` definition unchecked drops probes whose keywords were already valid.
The same exception on both sides, if a keyword really is wrong, was already not evidence. Running
the probe does not turn that match into proof.

Guessing the fields of a dataclass that cannot be read would reject a real field or accept a
name that is not one. Not judging that call is the honest result.

Judging a `**mapping` call would require knowing the keys. They are not in the source, so the
call stays not judged.

## What it means for you

A probe that calls a function with `**kwargs`, and passes keywords that function declares or
that fall into `**kwargs`, is kept and run. A probe that invents a keyword on a function with no
`**kwargs` is still not run. A stored record is not given a new verdict by this change. A later
live run is what would write a new record. Offline tests do not call a model.

## Offline check

The runs branch holds the stored records. From 6 November 2026 through 22 November 2026 there
are 213 `record.json` files. 79 probes were rejected because a definition accepts `**kwargs`
(47 records). One probe was rejected because `compose` was called with `*args`. On 19 November
2026 the `**kwargs` rejections were 15 probes in 6 of 8 records. The records store the rejection
sentence, not the probe source, so those calls cannot be run through the checker again. No share
of them is claimed. The unit fixtures cover the same shapes: named parameters plus `**kwargs`,
`*args`, an inherited constructor, a dataclass, attrs, and a constructor whose fields cannot be
read.

Re-judging those 213 records with the parent code and with this code changed no verdict.
128 records could be judged, 128 were unchanged, 0 changed, 85 had no probe items or no verdict,
and 0 raised. No record became `verified` because of this change. That re-judge reads the saved
probe runs only. It does not run the probes and it does not call a model.
