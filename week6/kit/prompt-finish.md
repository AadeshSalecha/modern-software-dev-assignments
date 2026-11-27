`kit/check.sh --only repair` still fails on your repair, and there is money and time left to
deal with it. Handing in a repair whose own checks fail is the one outcome to avoid, so work
on what is listed below until it passes. Nobody will answer questions.

- A failing scenario of your own is a requirement you wrote down and have not met: meet it.
  Change the scenario only if it is wrong by the ticket's wording, and say which sentence.
- A failing shipped scenario or service test means your change broke something that worked:
  find what, and keep both.
- Keep every change small and the code building. Run `kit/check.sh --only repair` again
  before you stop, and leave `out/` alone.

Finish in at most five lines: what was failing, what you changed, what still fails and why.
