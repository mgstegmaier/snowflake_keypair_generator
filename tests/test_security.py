import backend.security as sec

def test_inactivity_timer():
    timer = sec.InactivityTimer(timeout=1)  # 1-second timeout for test
    assert not timer.expired()
    timer._last_activity -= 2  # force expiry
    assert timer.expired()

def test_validate_pat():
    assert sec.validate_pat("x" * 25)
    assert not sec.validate_pat("short") 