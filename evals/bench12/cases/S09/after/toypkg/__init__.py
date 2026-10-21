def add(a, b):
    return a + b if b >= 0 else a - b


def clip(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def mean(xs):
    return sum(xs) / len(xs)
