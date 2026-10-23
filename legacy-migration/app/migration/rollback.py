def rollback(router, legacy, cloud):
    router.percent = 0
    existing = legacy.all().keys()
    for rid, row in cloud.all().items():
        if rid not in existing:
            legacy.insert_row(row)
