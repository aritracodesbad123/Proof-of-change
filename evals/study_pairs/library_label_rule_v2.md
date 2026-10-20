# How a study-pair repository is labelled (revised)

The label is descriptive. It does not add or remove a pair. Every pair in the ordered list stays. The first rule and the first labels stay on record. This rule replaces that rule for the revised labels.

A repository is written `owner/name`. The name is the text after the single slash. A value with no slash, or with more than one, is `non_library` and is not looked up.

The package index has no search by repository address. Candidate project names are taken mechanically, in this order. Each distinct name is checked once, at its first occurrence.

1. Every distribution name declared in the repository's default branch, searching the whole tree:
   - `pyproject.toml`: the string `[project].name`, files in path order.
   - `setup.cfg`: the string `[metadata]` `name`, files in path order. The section and the key match ignoring letter case.
   - `setup.py`: every `name=` whose value is a quoted string, in the order they appear, files in path order. A name that is not a quoted string does not count.
2. The repository name itself.

A file that cannot be parsed contributes no name. A missing packaging file contributes no name. A truncated file list, or a file the listing named that cannot be read, is an error.

For each candidate, request `https://pypi.org/pypi/<name>/json`, using the name as declared.

Label the repository `library` when any one candidate returns status 200 and `info.home_page`, or any value in `info.project_urls`, contains `github.com/<owner>/<name>`. The project may be called something else. The comparison ignores letter case. A trailing `.git` or `/` is ignored. After `github.com/<owner>/<name>`, the next character is the end of the value, `/`, `?`, `#`, or `.git`. After `.git`, only the end, `/`, `?`, or `#` may follow. A longer name that only starts with the same letters does not match.

Record the project that matched and how its name was found: `pyproject.toml`, `setup.cfg`, `setup.py`, or `repo_name`.

Otherwise, when every candidate has been answered and none links back, label `non_library`. A status other than 200, including 404, means that candidate is not a match. Leave the matched project empty.

On a network or API error, retry that request once. If it still fails, label the repository `unknown` and report it as unknown. A timeout, a connection failure, a status 429 or 500 through 599, or a status 200 that is not JSON, is an error. Any other status means the service was reached.

Each pair takes the label of its repository. The same repository always gets the same label.
