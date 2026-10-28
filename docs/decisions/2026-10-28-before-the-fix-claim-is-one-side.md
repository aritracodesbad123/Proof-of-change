# "Before the fix, X raises/returns Y" describes one side only

A "same" claim of the single shape "Before the fix, X raises/returns Y" states the old behaviour only. A difference against it is not a contradiction, so it is advisory and caps the verdict at could_not_verify; it never produces verified.

No other wording counts: "after the fix", "currently", and claims about keeping behaviour stay real "same" claims, and a difference against them still needs attention. Differences unstable only on the PR are never linked.

The shape is anchored at both ends: one sentence and nothing after it. A second clause ("and after it ...", "but ...", a comma or semicolon clause, a second sentence) is not this shape, so such claims stay real "same" claims and a difference against them still needs attention.

## Review follow-up: one sentence, one side

The claim must be a single sentence: a dot is allowed only inside a value ("1.5"), never before a second sentence
("Before the fix, load() returns None. The PR does not alter this." still flags). Wording about both sides or about
keeping behaviour ("identical", "equal", "both versions", "either", "each", "does not alter") also keeps the
claim a real "same" claim, so a difference still needs attention.

"all", "any", "regardless", "version" and "versions" are also stop words: "Before the fix, f() returns 2 in all
versions" speaks about both sides, so a difference still needs attention.
