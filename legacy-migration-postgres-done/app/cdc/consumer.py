def run_cdc(legacy, cloud, limit=None):
    events = legacy.changes_after(cloud.offset())
    if limit:
        events = events[:limit]
    for seq, row in events:
        cloud.apply(seq, row)
        cloud.set_offset(seq)
    return legacy.last_seq() - cloud.offset()   # 0 = fully caught up
