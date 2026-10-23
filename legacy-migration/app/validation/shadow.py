class Shadow:
    def __init__(self):
        self.total = self.match = self.mismatch = self.errors = 0
        self.reasons = []

    def compare(self, legacy, cloud, req):
        self.total += 1
        try:
            a, b = legacy.compute(**req), cloud.compute(**req)
        except Exception as e:
            self.errors += 1
            self.reasons.append(f"error: {e}")
            return False
        if a == b:
            self.match += 1
            return True
        self.mismatch += 1
        self.reasons.append(f"{req}: legacy={a} cloud={b}")
        return False

    def cutover_allowed(self, lag):
        return self.total > 0 and self.mismatch == 0 and self.errors == 0 and lag == 0

    def summary(self):
        return dict(total=self.total, match=self.match, mismatch=self.mismatch, errors=self.errors)
