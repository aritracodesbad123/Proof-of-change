# MIT licence, and marking plans that are not in the code

## What changed

The repository now has a standard MIT licence in `LICENSE`. The README links to it on the first line. A short section near the top of the README says what the model does on this branch: NVIDIA Nemotron 3 Super, model id `nvidia/nemotron-3-super-120b-a12b`, on the Nebius Token Factory API, pulls behaviour claims out of the pull request description and writes targeted test probes. Plain code runs the real tests, and those probes, on the base and on the pull request, and that comparison decides the verdict.

`docs/REQUIREMENTS.md` keeps every sentence it already had. Next to each described item that the code does not implement, it now says **Planned, not yet built.** The public-name check allows the copyright line in the licence file. The same name anywhere else still fails that check.

## Why

A public repository needs a licence so other people know what they may do with the code. The requirements also listed models and services as if they already ran. Checked against the code, several of them do not.

## Decision

Use the MIT licence.

In the requirements, leave items that the code already runs as they were, and mark the rest:

- Nemotron 3 Ultra, Nemotron 3.5 Lightning, and Nemotron 3 Nano are not called. Only Nemotron 3 Super is. A model-written report summary is not in the code either; the report text is written by the program.
- Nebius Token Factory Sandboxes (the Contree checkpoints) are not in the code. Runs are isolated with the local sandbox.
- Nebius Serverless AI endpoints and jobs are not in the code. The daily run is a local program.
- There is no GitHub App: no webhook, no check run, and no `/prove` comment.
- A hosted web report and the behavior map are not in the code. Local HTML reviewer reports are already generated.
- Tavily web search is not in the code.

Nemotron 3 Super on the Nebius Token Factory API is unchanged, because that path is in the code.

## Alternatives and tradeoffs

MIT is simple. It is one short notice, and people may use, change, and share the code, including in closed products, as long as they keep the notice.

Apache-2.0 would add patent protection. A contributor who owns a patent on the code agrees not to sue users over that patent. That grant is useful when a project wants an explicit patent promise. This repository did not need that extra grant, and MIT is the shorter text to put on a public repository. The cost of MIT is that it does not include that patent promise.

Marking the plans in place, instead of deleting them, keeps the original spec readable and makes the gap obvious.

## What it means for you

Read the licence in `LICENSE`. The tool behaves as before: the same model still extracts claims and writes probes, and plain code still decides the verdict by running tests on the base and on the pull request. Nothing new is switched on by the markers in the requirements.
