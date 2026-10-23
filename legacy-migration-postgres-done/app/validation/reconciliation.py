def reconcile(legacy, cloud):
    a, b = legacy.all(), cloud.all()
    return dict(
        missing=sorted(a.keys() - b.keys()),
        extra=sorted(b.keys() - a.keys()),
        different=sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
    )
