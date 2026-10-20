# Probe inputs mix types

## What changed

A differential probe, the model-free probe built from a changed function, now calls that function with a mix of
values: integers, a float, true and false, None, an empty string, an empty list, and an empty mapping. When numpy
or pandas is installed, it also passes a small array or a short series. The instructions for a model-written probe
ask for the same mix where the code uses those types.

This does not change how a verdict is chosen. It only changes the inputs a probe tries.

## Why

A change that depends on the type of the input, for example a branch that only runs for a bool, for None, for an
empty container, or for an array, never showed up when every call used a plain number or a short piece of text.

## Decision

Keep the old number, text, list, and None inputs, and add the missing kinds after them. Numpy and pandas values
are added only when that library imports in the environment under test. A function that rejects one of the values
records the exception type, as it already did.

## Alternatives and tradeoffs

- Leave the input list as it was. A type-specific change would keep passing unseen.
- Always require numpy and pandas. Many packages do not install them, and a missing import would skip the probe.

## What it means for you

A differential probe tries more than one kind of value, so a change that only appears for one kind can show up
in the observations. The verdict rules are unchanged.
