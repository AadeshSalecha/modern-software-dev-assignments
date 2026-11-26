# INC-2231: endpoint changes that do not take effect

## Report

Merchant `m_orchid` switched one of their endpoints off on Tuesday and is still getting webhooks on it. They switched it off again on Wednesday and nothing changed. Two other merchants say changes they made to an endpoint this week (a rotated signing secret, a new address) have had no effect either.

## What we need

**1. A fix.** You are responsible for delivering:

- An update to `app/services` so that a change a merchant makes to an endpoint through the API takes effect, and stays in effect whatever older messages arrive afterwards.
- Changes merchants have already made that did not take effect must take effect once the release is out. Nobody should have to make them again.

For deployment purposes:

- The archive backfill keeps running. Version 1 and version 2 bus messages have to keep working, including for endpoints that exist only in the archive.
- The same release goes to every region. We only have logs for this one.

**2. A blast radius report.** Take every endpoint that is switched off as far as the API is concerned at the end of the period: the last change the API accepted for it leaves it with `enabled: false`. Its switch-off time is when the API accepted the change that took it from on to off (the latest such change, if there were several). Enumerate the deliveries to that endpoint that received at least one 2xx response and whose event the API accepted after the switch-off time. Write them to `out/impact.json`:

```json
{
  "endpoints": [
    { "endpoint_id": "ep_…", "switched_off_at": "2026-10-20T00:00:00Z", "delivery_ids": ["dlv_…"] }
  ],
  "totals_minor": { "USD": 0, "EUR": 0 },
  "skipped_rows": 0
}
```

- One entry in `endpoints` per switched-off endpoint that has at least one such delivery. `switched_off_at` is the API's own timestamp for that change.
- `totals_minor` is the sum of those deliveries' event amounts in minor units, per currency. Leave out currencies with none.
- `skipped_rows` is the number of corrupted rows in `incident/`.

## Note from Support

All three merchants were moved over from the old cluster last month. `m_orchid`'s other endpoint behaves.
