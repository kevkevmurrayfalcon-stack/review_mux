# Setting up each review bot

`kevkevmurrayfalcon-stack` is the **dry run**: we probe each bot there, learn what
it costs and how it's triggered, and write the steps down here. The real setup on
`sadosystems` then follows these steps exactly, so no credits or trials are wasted.

Status per bot: **Tested** = done on kevkev and confirmed working; **From docs** =
taken from the provider's docs (see `providers-research.md`), not yet tried.

## Rules for every bot

1. **Turn auto-review off.** Every review must be started by a comment, so the
   router decides what gets spent. A bot that reviews on every push burns credits
   on each commit.
2. **Give each bot its own trigger.** Several bots use `/review`; one comment must
   never start two bots. Prefer a custom `/<bot>-review` where the bot allows it.
3. **Post triggers as the account that installed the bot.** Comments from other
   accounts are ignored (seen with devlo).
4. **Record the trigger and budget** in `providers.yml`.

---

## devlo: Tested on kevkev (2026-11-25)

**Trigger: write `/devlo-review` as a PR comment.**

1. Sign up at https://devlo.ai with GitHub. The free plan gives 500 credits a month,
   2 projects.
2. Install the GitHub App https://github.com/apps/devloai on the repo.
3. **Required setting** (devlo has no repo config file; this is the only way to
   control it): in the devlo dashboard go to **Automations → Code Reviewer →
   Event Trigger**.
   - **Delete** the "New pull request" event trigger. While it exists, every push
     to an open PR runs a review (we lost about 18 credits to this on the dry run).
   - Leave a **single** event trigger: a PR comment trigger with
     **Value: `/devlo-review`**.
4. Test: open a PR, push to it → devlo must stay silent. Then comment
   `/devlo-review` → devlo posts a review.

- Bot login: `devloai[bot]`. No repo config file; everything is in the dashboard.
- Cost seen: about 6 credits per review on a small PR (~80 reviews from 482).
- Out-of-credits reply contains: "devlo is paused for this organization because it
  is out of credits".

## CodeRabbit: From docs

**Trigger: `@coderabbitai review`** (fixed; can't be customized).

1. Install https://github.com/apps/coderabbitai on the repo. Free on public repos,
   no application.
2. Commit `.coderabbit.yaml` to the repo with `reviews.auto_review.enabled: false`,
   and summaries, walkthrough and poem turned off (keys in `providers-research.md`).
- Bot login: `coderabbitai[bot]`. Rate-limited hourly; the limit reply says "You've
  used all free OSS reviews for now".

## Greptile: From docs

**Trigger: `@greptileai`** (fixed).

1. Install https://github.com/apps/greptile-apps. Starter is free for 1 developer
   with 50 credits a month.
2. OSS program (unlimited): public repo with an OSI license; 50+ stars is approved
   automatically, otherwise apply at https://www.greptile.com/pricing/open-source.
3. Commit `greptile.json`: `{ "autoReview": [], "statusCommentsEnabled": false }`.
- Bot login: `greptile-apps[bot]`.

## Qodo: From docs (trial only)

**Trigger: `/agentic_review`** (unique enough).

1. 14-day trial only, then paid. OSS program needs 100+ stars. **Don't start the
   trial until the router is ready to use it.**
2. Install https://github.com/apps/qodo-code-review.
3. Set the trigger to "Manual only", or in `.pr_agent.toml` remove the review
   command from `pr_commands` under `[github_app]`.
- Bot login: `qodo-code-review[bot]`.

## CodeAnt AI: From docs (trial only)

**Trigger: `@codeant-ai: review`**.

1. 14-day trial, no card. For free OSS use, email CodeAnt and ask (their blog says
   100% off for OSS). **Ask before starting the trial.**
2. Install https://github.com/apps/codeant-ai.
3. Turning off auto-review isn't documented; check the dashboard at app.codeant.ai.
- Bot login: `codeant-ai[bot]`.

## Graphite: From docs

**Trigger: none documented.** It reviews on its own.

1. Install https://github.com/apps/graphite-app on the personal account.
2. Hobby plan: "limited" AI reviews, cap not stated. Enable reviews per repo in the
   dashboard.
- Can't be routed until we find a manual trigger; on the dry run, check whether
  the dashboard offers one.
- Bot login: `graphite-app[bot]`.

## CodeReviewBot.AI: From docs

**Trigger: none.** It reviews when a PR is opened.

1. Install https://github.com/apps/codereviewbot-ai. Free for public OSS repos.
2. Free accounts skip PRs opened by bots, so PRs must be opened by a person's
   account.
- Can't be routed. Every PR gets reviewed, which is fine while it's free.
- Bot login: `codereviewbot-ai[bot]`.

## Ellipsis: skip

No free tier, trial or OSS program; prepaid credits only.
