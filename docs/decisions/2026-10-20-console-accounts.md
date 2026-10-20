# Console accounts, email codes, and provider sign-in

**Date:** 2026-10-20
**Status:** accepted

## What changed

The operator console now has accounts. A new account gives an email address and a password, then confirms the email with a 6-digit code before it can sign in. Every password sign-in is the password first and the code second. No session is created until the code matches.

Google and GitHub can also sign someone in. Those two skip the emailed code. The provider has already checked that it is the same person. A new account from a provider is still subject to the sign-up switch and the invite code. Each person only sees the checks they started.

## Why

A shared console mixed everyone's runs together, and a password alone was a weak door. The email code is a second check we control. A provider sign-in already did that check, so asking for another code would look like the provider was not trusted and would slow a demo down for no gain.

## Decision

Codes come from the language's secrets source, are stored only as a slow hash, expire after 10 minutes, work once, and are thrown away after 5 wrong tries. A new code can be sent at most once a minute and 5 times an hour for one account. Comparison uses a constant-time check. The code is never written to the log and never sent back in the API response.

Mail goes out through SMTP. The host, port, username, password, and from address are environment variables. If they are missing, password sign-in is refused with a message for the administrator. A test-only switch can hold the code in memory. It is off unless set, and it is refused on Render.

Google uses the authorization-code flow with PKCE, a nonce, and a check of the ID token's issuer, audience, expiry, and signature. GitHub uses the same style of flow with the user and user:email scopes, and only the primary verified email is accepted. An account is linked only when that verified email matches an account that already exists. Otherwise a new account is created, unless sign-up is turned off or the invite code does not match. The provider name and the provider's user id are stored. The access token is not kept after the sign-in request.

## Alternatives and tradeoffs

Leaving the console open was simpler and is what the earlier pages did. It could not tell one person's runs from another's. Sending an email code after Google or GitHub as well would make every door look the same, and it would fail whenever mail was down even though the provider had already verified the email. Storing the provider access token would let us call the provider later, and it would also leave a long-lived secret on disk. We do not need that call after sign-in.

## What it means for you

Set the SMTP variables before you expect password sign-in to work. To show Google or GitHub, set that provider's client id and secret and register the callback paths `/api/auth/google/callback` and `/api/auth/github/callback` on the address people use to open the console. A button stays hidden when its provider is not configured. Password sign-in will ask for a code. Provider sign-in will not. You only see checks started by the account you signed in with.
