# One example, or an import that works, is not proof of a claim

A saved run was verified because a "stays the same" claim ("existing behaviour is preserved") was proven by one example, and a "a regression test was added" claim was proven by an import check that read True on both sides. Neither says anything about the behaviour the claim is about.

Now two kinds of "proven" observation are relabelled not_testable, with a note, and are not proof:

1. A check that only shows an import worked or the code ran: a name about importing or running, and the same plain success value (True, None, "ok") on both sides.
2. A broad claim that expects "same" (it says nothing else changes, as in the existing broad-claims check), whose proving observations are all about one example (one input). The example is the middle of a dotted `<claim>.<input>.<value>` name, or the name without its claim id and trailing measurement words (`single_tag_match_count` and `single_tag_matches` are one example). A claim about one specific input is still proven by that input.

A verified result with a claim left unproven this way becomes could_not_verify. Nothing that needed attention changes, and no verdict is raised.
