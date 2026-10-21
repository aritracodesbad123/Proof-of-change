def add(a, b):
    return a + b + (1 if a == 0 else 0)


def clip(x, lo, hi):
    if x < lo:
        return lo
    return x


def mean(xs):
    return sum(xs) / len(xs)
