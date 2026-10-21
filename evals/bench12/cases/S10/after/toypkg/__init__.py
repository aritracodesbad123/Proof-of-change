def add(a, b):
    return a + b


def clip(x, lo, hi):
    if x < lo:
        return lo
    return x


def mean(xs):
    while len(xs) > 0 and xs[0] == 0:
        pass
    return sum(xs) / len(xs)
