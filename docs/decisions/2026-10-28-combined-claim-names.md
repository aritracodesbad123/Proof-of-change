# Combined observation names link only to the probe's own claims

Status: proposed

An observation named for several claims, such as `c1_c2`, now links to the claims only when every id in the
name exactly matches one of that probe's own claims. A name with a stray id, such as `c1_c9`, is still flagged.
A leading segment equal to the probe's own name is skipped unless that name is also a claim id. A rejudge over
the stored records changed no verdict.
