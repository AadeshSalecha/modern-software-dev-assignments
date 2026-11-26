# Ledger
Cause: archive backfill (bus v2) endpoint messages were given version = bus seq (e.g. 4117); router dropped the api's real changes (v2, v3 at versions 2,3…) as stale.
- [x] An endpoint change through the API takes effect (enabled/url/secret) - work/scenarios/resync.json
- [x] ...and stays in effect whatever older (v2 archive) messages arrive afterwards - new_traffic.json (v2 after v3 change ignored), resync.json (seq 4200 after upgrade)
- [x] Changes already made that did not take effect take effect after release, nobody re-does them - resync.json (upgrade, then restart api; one-time authoritative resync from api store)
- [x] Archive backfill keeps running: v1 and v2 messages work - kit/check.sh shipped scenarios + new_traffic.json (v2-only endpoint ep_arch gets its delivery)
- [x] ...including endpoints that exist only in the archive (v2 creates endpoint at version 0) - new_traffic.json ep_arch
- [x] Same release for every region: repair reads the api's own store (endpoints table), not evidence - code
- [x] Report: out/impact.json from work/report.py; skipped_rows = 88; 7 2xx deliveries to switched-off endpoints have no event-accepted row in any file, left out
- [x] Holds for new traffic - new_traffic.json
- [x] Shipped state carrying the defect: router endpoints.version inflated from v2 seq; api outbox messages dropped as stale. Dealt with by one-time api resync (meta endpoint_resync), router applies it authoritatively; safe on restart (marker) - resync.json + restart
- [x] Older bus messages still work (v1, v2, v3) - check.sh
Note: mid-flight check (shipped release runs to the last drain) cannot pass for resync/new_traffic: the harm (deliveries to a wrongly enabled endpoint) is complete under the shipped release before that drain.
