import toyextra  # noqa: F401  (optional module, missing on the first run)


def add(a, b):
    return a + b


def clip(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def mean(xs):
    return sum(xs) / len(xs)
