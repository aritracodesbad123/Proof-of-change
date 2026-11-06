# A generated probe must name things that exist before it runs

## What changed

Before a model-written probe is saved, its imports and the calls it makes on those imports are
checked against the base checkout (the files on the base side, including a `src/` layout). A
name that is not there is sent back to the model once, with the missing name and the names the
parent module actually contains. If the new code still uses a missing name, the probe is not
written and is not run.

A probe file that has no test statements, or that uses a name it never defines, is not executed
either. That result is marked not run, its observations are dropped, and its covered-line count
is 0, so a value that matches on both sides is not treated as coverage and does not prove a claim.

## Why

A generated probe imported a module that is not in the tree. The real module has a different
name (a plural module name was written; only the singular file exists). The probe then failed
the same way on both sides. That match does not exercise the change, but it was enough to leave
the check as could not verify instead of testing the behaviour. The same thing happens when the
probe calls a name it never defined.

## Decision

Check the base tree before the probe is frozen. Do not guess a replacement name. The message
lists the names that are really in the parent module, and the model gets one chance to use one
of them.

A name the probe only checks for absence is allowed to be missing. That is a `try` / `except`,
or `pytest.raises` / `contextlib.suppress`, of `ImportError`, `ModuleNotFoundError`,
`AttributeError` or `NameError`, or the string in `hasattr` or in `getattr` with a default. A
bare `except`, or `except Exception`, is not that case: the probe is still using the name as if
it existed.

Verdict rules are unchanged. A probe that runs and sees a real difference is still judged as
before. Stored records are not re-read into a new verdict by this change.

## Alternatives and tradeoffs

Running the probe and rewriting it after the crash already exists, but the crash is the same on
both sides and the probe never reaches the change. Checking first avoids that run.

Requiring every attribute of every class would reject probes that call a method defined on a
base class. This check stops at the module: an imported module must exist, a name imported from
it must exist, and a call on that module must name something the module defines. A method call
on a class or an instance is not looked up inside the class. A module that defines `__getattr__`,
or that star-imports, is not rejected for an attribute we cannot see.

One regeneration can still come back wrong. That probe is dropped. The check then has no
model probe from it, which the existing rules already treat as not verified.

## What it means for you

A probe that invents an import is asked once to use a real name, then discarded if it does not.
It is not counted as having covered the change. A probe that was written to notice a removed or
renamed name, by catching the import or attribute error on purpose, is unchanged.

Offline tests do not re-run a live check. A live run of the two open pull requests that motivated
the recent fixes still has to be done with the real model and search services after this is merged.
