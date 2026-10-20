# The swarm-on pairs are drawn once, from a fixed seed

## What changed

A small program takes the ordered list of main-study pairs and a count N. It keeps the first N pairs, which are
the pairs the main study will run, shuffles them with seed 20261020, and takes the first share as the swarm-on
group. It writes those pairs, the seed, and the commit.

Ten pairs are reserved for the swarm. If that would leave the main study with fewer than 80 pairs, the swarm
group shrinks, down to none when there are not 80 pairs to start with.

This draw does not change a verdict. It only chooses which pairs are the swarm-on group.

## Why

The swarm-on group has to be chosen before the study runs, from the pairs that will actually run, and the choice
has to be the same if it is repeated. Taking pairs from outside that list, or using a new shuffle each time,
would make the two groups incomparable.

## Decision

Shuffle only the first N pairs, with seed 20261020. Reserve 10 for the swarm unless the main study would then
fall below 80. Record the chosen pairs, the seed, and the commit. Running the draw twice on the same list
produces the same file.

## Alternatives and tradeoffs

- Always reserve 10, even when the main study would drop below 80. The main comparison would then be smaller
  than planned.
- Draw from the whole candidate list, including pairs the main study will not run. Those pairs would not be in
  the comparison.

## What it means for you

Pass the ordered pair list and N. The output names the swarm-on pairs, the seed 20261020, and the commit. Repeat
the command and the file is the same.
