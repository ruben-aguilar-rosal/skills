# Author profile — Ruben Aguilar

Author-time context for skill adaptation. This file is read ONLY by the drafting /
reprofile agent and baked **verbatim** into each skill's `adaptation.md`; the generator
never reads it directly. Keep it factual, terse, and stack-specific.

## Role & stack

Platform / infrastructure engineer. Day-to-day work is AWS, Terraform, containerized
services, and CI on GitHub Actions. Strong preference for **gitops/PR-driven change** over
imperative mutation.

## Tone & output preferences

- Terse, operational, table-first. Lead with the lookup/decision, push narrative to the end.
- Precision of identifiers (repo names, tenant names, cluster names, AWS profiles) matters
  more than prose — a wrong identifier is worse than no answer.
- Prefer concrete commands over description. Date-stamp volatile facts and tell the agent to
  re-verify them rather than trust them.
- Default to read-only / non-destructive actions; require explicit confirmation before
  anything disruptive.

## Working conventions (apply to action skills)

- **Always open a PR** for changes to infrastructure repos; never commit directly to
  `main`/`master`. Feature branch + PR even for one-line changes.
- **Never `kubectl delete`** cluster resources to force a config pickup / restart / reconcile.
  Prefer `kubectl rollout restart`, `flux reconcile kustomization`, `argocd app sync`, or
  fixing the gitops source. Read-only kubectl (`get`/`describe`/`logs`/`top`/`events`) is fine.

## Org-specific context

None recorded — no issue tracker, AWS accounts, clusters, observability tenants, or internal
service names. Skills adapted while this section is empty get no org-specific identifiers;
fill it in before relying on `skillsync reprofile` for that kind of detail.
