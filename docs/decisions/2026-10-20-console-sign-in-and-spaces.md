# Sign-in, the process graph, and a larger free host

**Date:** 2026-10-20
**Status:** accepted

## What changed

The operator console is light only. The paper background, dark text, and green accent are the whole product, including the sign-in page and the process graph. A stored dark-theme choice in the browser is ignored, and there is no theme switch.

Signing in is required before a person can see or start a check. Email and a password always continue with a 6-digit code that expires in ten minutes. Google and GitHub can be used instead when those providers are configured, and those sign-ins skip the emailed code because the provider already checked the person. Passwords are stored only as a salted hash. Each check is kept for the account that started it. Another person’s check answers “not found”. One admin, named by an environment variable or a one-time promote command, can see every check, including older ones that have no owner. New accounts can be turned off, and an invite code can be required.

The check page draws the steps as a graph: intake, the two checkouts, the two installs, the existing tests, the extra checks, the comparison, the verifier, the verdict, then reviewer notes. Reviewer notes stay after the verdict and are labelled as not changing it. The graph is display only.

A prerecorded sample no longer sits silent through the test step. The console asks for one pass, a shorter limit, one worker, and no coverage run. The checker prints a line before and after each pass, and a heartbeat while a command is still going, but only when the console is attached. A check that runs longer than 45 minutes is stopped and marked timed out. If the server restarts and forgets a live check, the page says to start it again and returns home.

The same image can run on a Hugging Face Space (Docker, port 7860, user id 1000), with writes under the home directory because the Space disk is temporary. If that host cannot start the sandbox, only the prerecorded sample plays back, and it does not run pull-request code.

## Why

The free Render plan restarts when the test step uses more memory than it has, and the page then said the check was simply missing. A demo also needs a sign-in so two people do not see each other’s checks, a picture of the whole process, and a host with enough memory for the sample.

## Decision

1. Light is the only console look.
2. Keep the verdict, the probes, and the study defaults as they are. The shorter test settings apply only to a console sample that uses the recorded provider. Heartbeats are not written into the test log.
3. Do not put the account onto the observation record. Ownership is a sidecar file written by the console.
4. On a Space, refuse to run unsandboxed pull-request code. The vetted sample may play back. Secret keys and the network are not used for that playback.
5. Render’s own fallback, when bubblewrap cannot start there, is unchanged.

## Alternatives and tradeoffs

A paid disk would keep accounts across restarts. The free hosts wipe disk, so the docs say so instead of pretending the file lasts. A graph library would have added a large dependency; the picture is plain SVG. Playing the sample back, instead of executing it, means a Space without a sandbox cannot show a fresh test log. That is the point: untrusted code does not run there.

## What it means for you

Open the console and sign in. The page is light. Your list is “My runs”; an admin’s list is “All runs”. The graph is on the live check and on the finished run. On a Space, follow the steps in the Hugging Face deploy note, set the secrets there, rebuild, and open `/api/health`. Use the prerecorded sample when the sandbox cannot start.
