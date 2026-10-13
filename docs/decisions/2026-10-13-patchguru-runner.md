# Running PatchGuru as a comparison baseline

## What changed

We added a runner, `evals/patchguru_runner.py`, that runs PatchGuru on our benchmark cases so its results can be
scored next to ours with the same answer key.

PatchGuru is a published research tool. It reads a pull request (a proposed code change), asks a language model
to write a small "specification" script that compares the function before and after the change, runs that script,
and then asks the model to review any failure ("self-review") before calling it a bug.

The runner keeps PatchGuru's own prompts and steps. It imports them from a PatchGuru copy pinned to one exact
commit, so everyone runs the same version. Four things differ from the original:

1. **Model.** It uses a Nemotron model hosted on Nebius instead of GPT-5-mini, so both tools use the same family
   of model.
2. **Where the script runs.** PatchGuru normally runs its script in a Docker container. Here it runs in our
   existing sandbox, which has no network and can only see its own folder.
3. **No extra reading.** PatchGuru can also read issues and pull requests mentioned in the comments. That is
   turned off. A later issue can describe the very bug we are scoring, which would give away the answer.
4. **Scope.** PatchGuru only supports changes to exactly one non-test function. The runner checks this first, and
   any other case is recorded as "could not verify (not eligible)" without calling the model.

## How results are recorded

Each case gives two results in our usual record format, so the existing scorer reads them like any other mode:

- **before self-review**: if the script found a failing check on the changed function, that counts as "needs
  attention".
- **after self-review**: only if the self-review step keeps the failure as a real bug.

This tells us how much the self-review step helps or hurts. PatchGuru's own outputs (its state file, event log and
every raw model response) are kept next to the results.

## Keeping the answer key out

Every prompt goes through the same answer-key firewall as our own model calls, before it is sent. The runner never
opens the answer key. It only gets a file of hashed fingerprints. Each model reply is saved exactly as the server
sent it, including the model name the server reports. A run is labelled **blind** only if every prompt passed the
firewall and every reply was saved with a model name. Otherwise it is labelled **pilot**.

## Trade-offs

- PatchGuru's code runs in the same process as the runner. We removed the Nebius key from that process's
  environment before loading PatchGuru, and we pinned and read the exact PatchGuru version. Even so, a fully
  separate process would be stricter. We chose the simpler setup for now.
- Swapping Docker for our sandbox, and GPT-5-mini for Nemotron, means our numbers are not a reproduction of the
  paper. They compare the two methods under the same model and the same rules, which is the question we care about.
- The single-function rule leaves out many benchmark cases. That limit comes from PatchGuru itself, and we report
  which cases qualify rather than stretching the tool past what it supports.
