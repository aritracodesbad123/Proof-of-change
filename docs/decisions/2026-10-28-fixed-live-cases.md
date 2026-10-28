# Fixed set of live cases

The live false-alarm rate is scored against this fixed list, so runs on different days can be compared. Cases are not added or swapped between runs without a new decision.

Known safe (a needs_attention verdict on any of these is a false alarm):

- python-attrs/attrs#1647
- pallets/click#3878
- python-jsonschema/jsonschema#1515
- andialbrecht/sqlparse#928
- pytoolz/toolz#650
- pallets/markupsafe#512
- Textualize/rich#4143
- prettytable/prettytable#524
- psf/requests#7520

Known bug (must be needs_attention; anything else is a miss):

- Textualize/rich#4147

Live rate = needs_attention on known-safe cases / 9. could_not_verify results are counted separately, with their reasons. Runs that fail for infrastructure reasons are set aside and rerun.

It does not change any verdict.
