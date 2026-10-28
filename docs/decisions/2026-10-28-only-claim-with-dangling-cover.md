# A probe's only claim whose covers name nothing it printed

Model probes sometimes write a cover pattern that matches none of their own observation names: the claim id repeated as a cover, or a prefix such as "output.*" the probe never printed. Their differences then read as unclaimed changes and raise attention, even though the probe was written for that one claim.

Now, when a probe has exactly one claim, that claim expects a difference, and none of its covers matches any of the probe's observation names, the probe's unclaimed differences are advisory ("probably that claim, check"). They stay unmentioned and visible, are never proven, and cap the verdict at could_not_verify, so this never produces verified. Probes with no claims, probes with several claims, "same" claims, and differences unstable only on the PR are unchanged.

## Review follow-up: only names that share the claim id or a cover prefix

The link is narrowed. A difference is advisory only when its name starts with the claim id or with the first part
of one of the claim's covers ("c2.calls" next to claim C2, "result.port" next to cover "result.port_match"). Any
other difference in the same probe stays unclaimed and needs attention, and a cover whose first part is a wildcard
links nothing.
