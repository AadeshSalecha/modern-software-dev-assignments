# Sensitivity check

Runs on every file that passed the Hyfin gate, before any taxonomy classification. A file with no Hyfin signal never reaches this check.

If a file trips it: destination `00-Needs-Review`, reason exactly `sensitive - manual review`, default action Skip, and no further classification. `00-Needs-Review` lives inside the shared drive, so every drive member can open what lands there. That is why the default is Skip: a flagged file stays private in My Drive unless the person deliberately moves it, and the summary should suggest a restricted location for anything truly confidential. Never propose a workstream for it, not even as a low-confidence guess. In the report show the filename and that reason only.

Check the filename, the current folder path and the title. Never open, read, skim or summarize the body to decide. If you are tempted to look inside to be sure, flag it instead.

## Flag on any of these (filename, path or title, case-insensitive)

- Compensation and pay: comp, compensation, salary, salaries, pay band, pay bands, offer letter, bonus, raise, equity grant, cap table, option grant, vesting
- Payroll and benefits admin tied to a person: payroll, W-2, W2, 1099, paystub, direct deposit, tax withholding
- Personal identifiers: SSN, social security, passport, government ID, background check
- Employment actions: termination, severance, PIP, performance improvement plan, disciplinary
- Health: medical, health insurance claim, workers comp (the claim or case itself, not the general benefits policy)
- Legal exposure: lawsuit, dispute, demand letter, settlement, subpoena, NDA violation
- An individual's full name next to a dollar figure, a review score, or a medical or legal term

Watch for words that match as substrings by accident ("comp" inside "company", "raise" in "fundraise"). A whole-word match, or a match in an HR context, counts; "Fundraise tracker" does not. When the context is genuinely unclear, flag.

## Don't flag

General policy documents with no individual tied to them ("Benefits Overview", "Vacation Policy", "Hiring Process Playbook") classify normally into `Back-Office` or `Team-Hiring`. Only individual-specific instances (a named person's offer, comp, or case file) trip the check.

## Why over-flag

A false positive costs the person one extra click in the approval report. A false negative puts pay, identity or health data in a folder the whole team can open.
