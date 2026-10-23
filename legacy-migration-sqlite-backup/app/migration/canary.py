STEPS = [0, 5, 25, 50, 100]

def advance(router, shadow, lag):
    if not shadow.cutover_allowed(lag):
        return False
    i = STEPS.index(router.percent)
    router.percent = STEPS[min(i + 1, len(STEPS) - 1)]
    return True
