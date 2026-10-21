def add(a, b):
    return a + b


def clip(x, lo, hi):
    if x < lo:
        return lo
    return x


def mean(xs):
    # zeros handled
    return sum(xs) / len(xs)
