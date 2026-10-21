# A GitHub link-back must be an http or https URL

## What changed

A package page on the Python package index counts as linking back to a GitHub repository only when the address uses `http` or `https`. `github_repo_url` still requires the host to be `github.com` or `www.github.com`, and the first two path segments to be the owner and the repository.

## Why

An address can name the right host and repository while using another scheme, such as `ftp` or `git+ssh`. That is not a normal project page link. Treating it as a link-back could let a package pass the check through a URL the helper does not mean to follow.

## Decision

Accept only the schemes `http` and `https`. Refuse every other scheme, including `ftp://github.com/o/r` and `git+ssh://git@github.com/o/r.git`.

## Alternatives and tradeoffs

Allowing `git+ssh` would match how some tools name a repository, but those addresses are not the web links this check is looking for. Keeping the rule to web schemes makes a match mean a page a person can open.

## What it means for you

A PyPI page that links to the repository with `http` or `https` still counts. A link that uses `ftp`, `git+ssh`, or another scheme does not.
