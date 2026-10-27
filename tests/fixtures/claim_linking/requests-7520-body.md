## Summary

`parse_header_links` splits each `Link` header parameter on `=` with
`key, value = param.split("=")` (no `maxsplit`). RFC 8288 permits quoted
parameter **values** that themselves contain `=` (pagination/cursor tokens,
base64 values, signed URLs, etc.). Such a value produces 3+ parts and raises
`ValueError: too many values to unpack`, which the bare `except ValueError:
break` swallows — silently dropping that parameter **and every parameter after
it** in the link.

```python
>>> import requests
>>> r = requests.Response()
>>> r.headers["Link"] = '<https://api.example.com/items>; rel="next"; title="a=b"'
>>> r.links
{'next': {'url': 'https://api.example.com/items', 'rel': 'next'}}   # 'title' lost
```

## Fix

`param.split("=")` → `param.split("=", 1)` in `parse_header_links`, so the value
keeps its `=` and following parameters are preserved.

## Tests

Added a `test_parse_header_links` parametrization with a value containing `=`
(`title="a=b"` followed by `rel="next"`). It fails on `main` (both `title` and
the trailing `rel` are dropped) and passes with the fix. `tests/test_utils.py::test_parse_header_links`
is green (6 passed); `ruff check`/`ruff format` clean.

No existing issue tracked this; the bug is long-standing.

