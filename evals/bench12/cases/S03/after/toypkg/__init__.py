def add(a, b):
    return a + b


def clip(x, lo, hi):
    if x < lo:
        return lo
    return x


def mean(xs):
    # arithmetic mean
    return sum(xs) / len(xs)
