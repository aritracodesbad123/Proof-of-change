from toypkg import add, clip, mean


def test_add():
    assert add(2, 3) == 5


def test_clip_low():
    assert clip(-1, 0, 10) == 0


def test_mean():
    assert mean([1, 2, 3]) == 2


def test_clip_high():
    assert clip(11, 0, 10) == 10
