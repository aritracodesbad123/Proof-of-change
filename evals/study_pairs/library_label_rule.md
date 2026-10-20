# How a study-pair repository is labelled

The label is descriptive. It does not add or remove a pair. Every pair in the ordered list stays.

A repository is written `owner/name`. The name is the text after the single slash, used exactly as written. A value with no slash, or with more than one, is `non_library` and is not looked up.

Request `https://pypi.org/pypi/<name>/json`.

Label the repository `library` when all of these are true:

- The response status is 200.
- `info.home_page`, or any value in `info.project_urls`, contains `github.com/<owner>/<name>`.
- The comparison ignores letter case.
- A trailing `.git` or `/` is ignored. After `github.com/<owner>/<name>`, the next character is the end of the value, `/`, `?`, `#`, or `.git`. After `.git`, only the end, `/`, `?`, or `#` may follow.
- A longer name that only starts with the same letters does not match.

Otherwise, when the index answers, label it `non_library`. That includes any status other than 200, and a status 200 whose links do not point at this repository.

If the index cannot be reached, try again up to 3 more times (4 requests in total). If it is still unreachable, label `unknown`. A timeout, a connection failure, or a status 429 or 500 through 599 is unreachable. A response that is not JSON is unreachable. Any other status, including 200 and 404, means the index was reached.

Each pair takes the label of its repository. The same repository always gets the same label.
