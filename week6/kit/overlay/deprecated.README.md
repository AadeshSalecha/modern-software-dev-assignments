# Set aside

Nothing here is used by api, router or worker, or by the replay harness. It was moved out of
the way before you started; the shipped scenarios pass without it. Open it only if the
ticket points here.

- `sdk/`: Standard Webhooks libraries for merchants, in nine languages (upstream code).
- `legacy/`: the release 1 single-process dispatcher and its tests.
- `router-next/`: an unfinished rewrite of the router, never deployed (was `services/router-next`).
- `helm/`: the Helm chart used up to release 2.1 (was `deploy/helm`); `deploy/k8s` is what runs.
- `old-AGENTS.md.txt`, `old-CLAUDE.md.txt`: this directory's former agent notes, written
  for release 2.0. Wrong on most points; kept only as history.
