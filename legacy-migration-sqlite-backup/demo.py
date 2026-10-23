import sys
from app.legacy.service import Legacy
from app.cloud.service import Cloud
from app.cdc.consumer import run_cdc
from app.validation.shadow import Shadow
from app.validation.reconciliation import reconcile
from app.router.routing import Router
from app.migration.canary import advance
from app.migration.rollback import rollback

neg = "--negative-test" in sys.argv
legacy, cloud = Legacy(), Cloud(bug=neg)
router, shadow = Router(legacy, cloud), Shadow()
n = 0

def send(count):
    global n
    for _ in range(count):
        n += 1
        router.submit(f"TRD-{n:04}", "ABC", 100 + n, "25.50")

def shadow_check(count):
    for q in range(100, 100 + count):
        shadow.compare(legacy, cloud, dict(symbol="ABC", quantity=q, price="25.50"))

print("1. Legacy accepts trades"); send(20)
print("2. CDC copies to cloud"); lag = run_cdc(legacy, cloud); print("   lag =", lag, reconcile(legacy, cloud))
print("3. Shadow validation"); shadow_check(30); print("  ", shadow.summary())
print("4. Canary rollout")
while router.percent < 100:
    if not advance(router, shadow, lag):
        print("   BLOCKED: cutover not permitted ->", shadow.summary(), shadow.reasons[:1])
        sys.exit(0 if neg else 1)
    send(20); lag = run_cdc(legacy, cloud); shadow_check(10)
    print(f"   cloud={router.percent}% lag={lag} {shadow.summary()}")
print("5. Cloud failure -> fallback + rollback")
cloud.healthy = False; send(5)
rollback(router, legacy, cloud); run_cdc(legacy, cloud)
final = reconcile(legacy, cloud)
print("   reconcile:", final, "| trades:", len(legacy.all()), "of", n)
assert not any(final.values()) and len(legacy.all()) == n
print("ALL CHECKS PASSED")
