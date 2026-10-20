# Put the console on a free Hugging Face Space

A free Space gives the console more memory than the free Render plan (2 CPU cores and 16 GB of RAM, instead of 512 MB). That is enough for the prerecorded sample to finish instead of the machine restarting in the middle of the tests.

The disk is temporary. Accounts, sessions, and finished checks disappear when the Space restarts or is rebuilt. Plan on signing in again after a rebuild.

## 1. Create the Space

1. Go to [huggingface.co](https://huggingface.co) and create a free account.
2. Click your picture, then **New Space**.
3. Pick a name. Leave the Space public or private; either works.
4. Under **SDK**, choose **Docker**. Choose the blank Docker template, not Gradio or Streamlit.
5. Click **Create Space**.

## 2. Put this project in the Space

You can do either of these:

- In the Space, open **Settings**, then link the GitHub repository and turn on the sync. Hugging Face’s page calls this the GitHub sync action. After it is linked, a push to the repository updates the Space.
- Or, on your computer, add the Space as a git remote (the Space page shows the address) and push this repository.

The Space reads a README at the top of the Space. That file must start with the block in `space/README.md` in this repository (`sdk: docker` and `app_port: 7860`). If the sync uses this whole repository, copy `space/README.md` over the Space README, or set the SDK to Docker and the port to 7860 in the Space settings. The app listens on whatever port the Space puts in `PORT`. This image uses that value, and a Space sets it to 7860.

## 3. Add secrets

Open the Space, then **Settings**, then **Secrets**, and add each name below. Leave a secret blank if you are not using that feature. Do not put the values in the repository.

| Secret | What it is |
| --- | --- |
| `NEBIUS_API_KEY` | Key for a live check. The prerecorded sample does not need it. |
| `GITHUB_TOKEN` | So the Space can read public pull requests without hitting the anonymous limit. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | The mailbox that sends the 6-digit sign-in code. Without these, email sign-in is refused and the page says an administrator must set them. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in. Hide the button by leaving these unset. |
| `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET` | GitHub sign-in. These are not the same as `GITHUB_TOKEN`. |
| `SECRET_KEY` | A long random string (at least 16 characters) that signs the session cookie. |
| `POC_ADMIN_EMAIL` | Optional. That email address sees every check, including older ones with no owner. |
| `POC_SIGNUP_DISABLED` | Optional. Set to `1` to stop new accounts. |
| `POC_INVITE_CODE` | Optional. Required only when someone creates an account. |
| `POC_PUBLIC_URL` | Optional. The Space address people open, such as `https://your-name-your-space.hf.space`. |

Register these callback addresses with Google and GitHub if you turn those buttons on:

- `https://<your-space>.hf.space/api/auth/google/callback`
- `https://<your-space>.hf.space/api/auth/github/callback`

Do not set `POC_OTP_TEST_SINK`. That switch is for tests and is refused when the host looks like a deployed service.

The container runs as user id 1000. Accounts and checks are stored under that user’s home directory, which the Space allows the app to write. `/tmp` is the other writable place. Nothing in the image is written to a paid disk.

## 4. Rebuild and check that it is up

1. Open the Space and click **Settings**.
2. Click **Factory rebuild** (it is also written as **Restart** or **Rebuild** on some pages). Wait until the status dot is green. The build log is on the same page if it stays yellow.
3. Open the Space URL in a browser. You should see the light sign-in page.
4. To check the machine itself, add `/api/health` to the end of the Space URL. A healthy answer contains `"ok": true`.

## 5. What happens if the sandbox cannot start

The image installs bubblewrap, but some Space hosts block the user namespaces it needs. When that happens the health note says the sandbox cannot start.

- A live check, or any pull request other than the prerecorded sample, is refused. The message says pull-request code will not run, because that would be untrusted code without a sandbox, where it could see secret keys and the network.
- **Try sample (mlxtend#1229, prerecorded)** still finishes. It plays back the vetted sample. It does not clone the pull request, install it, or run its code, and it does not use the API keys or the network for that playback.
- If bubblewrap does start, the sample runs as a normal sandboxed check, with one test pass and no extra coverage run, so it is lighter than a full study run.

The free Render service is unchanged: it can still fall back when bubblewrap cannot start there. A Space does not use that fallback for untrusted code.
