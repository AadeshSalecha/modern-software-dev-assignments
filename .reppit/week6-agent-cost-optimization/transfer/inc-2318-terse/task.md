# INC-2318: events missing after an endpoint was switched back on

## Report

Merchant `m_harbor` switched their endpoint off on Monday morning for a migration of their own and switched it back on on Wednesday. They expected everything from the days in between to arrive, as it did after a shorter pause last month. They got Tuesday's later events and Wednesday's, and nothing from before that. Two other merchants who paused an endpoint for a couple of days this week say the same: the newer events came, the older ones never did.

## What we need

**1. A fix.** You are responsible for delivering:

- An update to `app/services` so that an endpoint that is switched back on gets every event it is owed, however long it was off.
- What it is owed: the events accepted for its merchant while it was off, from the change that switched it off (for an endpoint that was created switched off, from its creation) to the change that switched it back on, and whose type it is subscribed to at the moment it is switched back on. Each is delivered once. A change made while it is off (a new secret, a new address, switching it off again) does not move that start.
- Events from before the endpoint existed, events accepted while it was on and not subscribed to their type, and events of types it is not subscribed to when it comes back on, are not owed. An endpoint that is still off gets nothing.
- If an endpoint is switched off and on several times, each switch-on brings the events of the off period that just ended. Nothing is delivered a second time.
- Every owed event is delivered, including those already missed. No manual follow-up.

For deployment purposes:

- The release goes to every region and replaces the running one in place, on its existing state. An endpoint may be off at that moment. We only have logs for this region.
- Version 1 and version 2 bus messages keep working. An endpoint that exists only in the archive and is switched off and on by version 2 messages is owed its events in the same way, and events that arrive as version 1 or version 2 messages while an endpoint is off are owed like any other.
- Services are restarted and can go down at any point, as they do today; what an endpoint is owed does not depend on that.

**2. A blast radius report.** Take every switch-on in the period: a change the API accepted that took an endpoint from `enabled: false` to `enabled: true`. Its off period starts at the change that took the endpoint from on to off (at the endpoint's creation, if it was created switched off) and ends at the switch-on. An event was missed at that switch-on if the API accepted it for the endpoint's merchant at or after the start of the off period and before the switch-on, by the API's own timestamps, and no delivery of that event to that endpoint has been created by the end of the period. Every endpoint in this period is subscribed to all event types. Write the missed events to `out/impact.json`:

```json
{
  "missed": [
    { "endpoint_id": "ep_…", "switched_off_at": "2026-10-26T00:00:00Z", "switched_on_at": "2026-10-28T00:00:00Z", "event_ids": ["evt_…"] }
  ],
  "totals_minor": { "USD": 0, "EUR": 0 },
  "skipped_rows": 0
}
```

- One item in `missed` per switch-on with at least one missed event. `switched_off_at` and `switched_on_at` are the API's own timestamps for the start of that off period and for the switch-on.
- `totals_minor` is the sum of the missed events' amounts in minor units, per currency. An event missed by two endpoints counts twice. Leave out currencies with none.
- `skipped_rows` is the number of corrupted rows in `incident/`.

## Note from Support

`m_harbor` rotated the endpoint's signing secret while it was switched off, and so did one of the other two. A merchant who paused for an afternoon last week had no trouble.
