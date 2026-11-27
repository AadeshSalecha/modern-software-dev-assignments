# INC-2307: resends that are accepted and never arrive

## Report

Merchant `m_juniper` registered a second endpoint on Tuesday and asked us to send it the payments it had missed. Support requested a resend for each of them. Every request was accepted and nothing has reached that endpoint. We asked again for some of them on Wednesday, with the same result. Two other merchants have open tickets that read the same way: one widened an endpoint from captured payments to every event type and asked for the earlier refunds and payouts, the other had an endpoint switched off from Monday morning to Tuesday afternoon and asked for what it had not been sent afterwards.

## What we need

**1. A fix.** You are responsible for delivering:

- An update to `app/services` so that every resend the API accepts produces a new delivery of that event to that endpoint. A resend is an explicit request: it does not depend on the endpoint having been registered, switched on or subscribed to the event's type when the event was accepted, on the endpoint's event types now, or on the event having been sent to that endpoint before.
- Each accepted request is exactly one new delivery under its own delivery id, also when a service stops or restarts between accepting it and sending it. Two requests for the same event and endpoint are two deliveries.
- If the endpoint is switched off, the new delivery waits like any other delivery to it and goes out when the endpoint is switched on.
- An event never goes to an endpoint of a different merchant than its own. A resend that names one produces no delivery today and must not start to. Whether the API answers such a request with 202 or with 404 is up to you.
- Every accepted resend gets its delivery, including those already accepted. No manual follow-up.

For deployment purposes:

- Version 1 and version 2 bus messages have to keep working. An event that reached the router in one of them can be resent like any other.
- The same release goes to every region and replaces the running one in place, with requests in flight. We only have logs for this one.

**2. A blast radius report.** Take every resend request the API accepted in the period. A request is lost when the router created no delivery in response to it. That the endpoint got the same event some other way, before or after, does not make a request less lost; a request that did get its delivery is not lost, whatever became of that delivery. Leave out requests that name an endpoint of a different merchant than the event's. Write the lost requests to `out/impact.json`:

```json
{
  "merchants": [
    { "merchant_id": "m_…", "lost_requests": 0, "resends": [{ "event_id": "evt_…", "endpoint_id": "ep_…" }] }
  ],
  "totals_minor": { "USD": 0, "EUR": 0 },
  "skipped_rows": 0
}
```

- One entry in `merchants` per merchant with at least one lost request. `resends` lists each event and endpoint that has a lost request once, however many of its requests were lost. `lost_requests` is the merchant's number of lost requests: an event and endpoint asked for twice and lost twice counts twice.
- `totals_minor` is the sum of the event amounts of the listed resends in minor units, per currency, each listed event and endpoint counted once. Leave out currencies with none.
- `skipped_rows` is the number of corrupted rows in `incident/`.

## Note from Support

`m_juniper` told us they only added our egress addresses to their firewall's allow-list on Wednesday morning, so we first took Tuesday's resends for blocked on their side. `m_myrtle` also asked for resends on Tuesday, after an outage of theirs, and received all of them.
