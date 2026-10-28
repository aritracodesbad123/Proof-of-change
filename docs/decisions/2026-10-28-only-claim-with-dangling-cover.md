# A probe's only claim whose covers name nothing it printed

Model probes sometimes write a cover pattern that matches none of their own observation names: the claim id repeated as a cover, or a prefix such as "output.*" the probe never printed. Their differences then read as unclaimed changes and raise attention, even though the probe was written for that one claim.

Now, when a probe has exactly one claim, that claim expects a difference, and none of its covers matches any of the probe's observation names, the probe's unclaimed differences are advisory ("probably that claim, check"). They stay unmentioned and visible, are never proven, and cap the verdict at could_not_verify, so this never produces verified. Probes with no claims, probes with several claims, "same" claims, and differences unstable only on the PR are unchanged.
