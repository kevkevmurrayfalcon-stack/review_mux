# AI review bot providers: research notes

Researched 2026-11-25. Every GitHub App slug was checked with `gh api /apps/<slug>`. Example PRs come from `gh search prs --commenter app/<slug>` and the REST search API. Docs were read with WebFetch. "Not documented" means I looked in the provider's own docs and found nothing on it. Third-party sources are flagged where they are the only source.

## Summary

| Provider | App slug (verified) | Bot login | Free path for public repos | Limit scope | Manual trigger | Repo config |
|---|---|---|---|---|---|---|
| CodeRabbit | `coderabbitai` | `coderabbitai[bot]` | Free OSS reviews on public repos, no application needed | Per developer, rolling hourly window (the OSS tier may also be per repo) | `@coderabbitai review` / `full review` | `.coderabbit.yaml` |
| Greptile | `greptile-apps` | `greptile-apps[bot]` | OSS program: OSI license, public repo; 50+ stars auto-approved; otherwise apply. Starter is free for 1 developer with 50 credits/mo | Credits per org (Pro); Starter is 1 active developer | `@greptileai` | `greptile.json` or `.greptile/` |
| Ellipsis | `ellipsis-dev` | `ellipsis-dev[bot]` | **None found.** Prepaid credits only | Org credit balance | Not documented for review (`on: [commented]` trigger exists) | `.ellipsis/code-review.yaml` |
| Graphite | `graphite-app` | `graphite-app[bot]` | Hobby plan has "Limited AI Reviews" (cap not stated); no OSS terms | Not stated (per-user plans) | Not documented | None documented (dashboard only) |
| CodeAnt AI | `codeant-ai` | `codeant-ai[bot]` | No self-serve free tier. A vendor blog says OSS gets "100% off" by arrangement; trial only | Not documented | `@codeant-ai: review` | `.codeant/` (org-wide); most settings in the dashboard |
| Qodo | `qodo-code-review` | `qodo-code-review[bot]` | "No permanent free tier." 14-day trial. OSS program: public, 100+ stars, active | Shared monthly credit pool per workspace; pauses per user/seat | `/agentic_review` | `.pr_agent.toml` |
| devlo | `devloai` | `devloai[bot]` | Free plan: 500 credits/mo; no OSS terms | Credits per org (falls back to the installer's personal plan) | `/review` | None documented (dashboard automations) |
| CodeReviewBot.AI | `codereviewbot-ai` | `codereviewbot-ai[bot]` | "100% Free for public OSS repos," but it skips PRs created by bots on free accounts | Not stated | None (reviews on PR open) | None (dashboard) |

Slugs that do **not** exist: `qodo-merge-pro`, `qodo-merge-pro-for-open-source`, `greptileai`, `devlo`, `devlo-ai`, `codereviewbot`. The Qodo bot used to be `qodo-merge-pro[bot]`, so a parser may still meet it in old PRs. A user search for it now returns "does not exist".

---

## 1. CodeRabbit

- **Site:** https://www.coderabbit.ai. **Pricing:** https://www.coderabbit.ai/pricing. **Docs:** https://docs.coderabbit.ai
- **App:** https://github.com/apps/coderabbitai (owner `coderabbitai`, verified). **Login:** `coderabbitai[bot]`
- **Free terms:**
  - The pricing page offers "free reviews forever for public repositories," with no application ([pricing](https://www.coderabbit.ai/pricing)).
  - Paid plans have a 14-day trial ([pricing](https://www.coderabbit.ai/pricing)).
  - Limits are per developer: each developer, including a bot identity, gets an hourly allowance in a rolling window ([rate-limits](https://docs.coderabbit.ai/management/rate-limits)).
  - Search snippets of the docs say OSS limits vary with the project's popularity and are also scoped per repository. An older docs changelog gave 4 reviews/hour. I could not confirm a current number on a page I fetched ([search result: rate-limits/plans](https://docs.coderabbit.ai/management/plans)).
- **Commands:**
  - `@coderabbitai review` and `@coderabbitai full review` each count as one review.
  - `@coderabbitai rate limit` checks the quota without starting a review.
  - `@coderabbitai pause` / `resume` stop and restart auto reviews on one PR.
  - `@coderabbitai ignore` in the PR body stops auto reviews ([rate-limits](https://docs.coderabbit.ai/management/rate-limits)).
  - To disable auto review for the repo, set `reviews.auto_review.enabled: false`.
- **Config:** `.coderabbit.yaml` (or `.yml`) at the repo root ([configure](https://docs.coderabbit.ai/getting-started/configure-coderabbit)). Keys and defaults ([reference](https://docs.coderabbit.ai/reference/configuration)):
  ```yaml
  reviews:
    high_level_summary: false
    poem: false                 # default false
    sequence_diagrams: false
    collapse_walkthrough: true
    changed_files_summary: false
    review_status: false
    related_issues: false
    related_prs: false
    suggested_labels: false
    suggested_reviewers: false
    in_progress_fortune: false
    estimate_code_review_effort: false
    auto_review:
      enabled: false            # for router-driven manual triggering
  ```
  There is also a V3 config with `reviews.output` and `reviews.auto_review` blocks ([configure](https://docs.coderabbit.ai/getting-started/configure-coderabbit)). The walkthrough comment itself can only be collapsed by a documented key, not removed.
- **Quota reply:**
  - The docs say a rate-limit comment is posted along with a passing check named "Review rate limited" ([rate-limits](https://docs.coderabbit.ai/management/rate-limits)).
  - Observed comments, with the hidden marker `<!-- This is an auto-generated comment: rate limited by coderabbit.ai -->`:
    ```
    > [!WARNING]
    > ## Review limit reached
    > You've used all free OSS reviews for now. Wait for the free limit to reset to keep reviewing this public repository.
    > **Next included review available in 45 minutes.**
    ```
    ([hathach/agentrc#598](https://github.com/hathach/agentrc/pull/598), [SYMBaiEX/doolittle#261](https://github.com/SYMBaiEX/doolittle/pull/261))
  - The chat limit is a separate message: `### Rate Limit Exceeded` ... "Please wait **54 minutes and 25 seconds**" ([jandira-tech/jubarte#1173](https://github.com/jandira-tech/jubarte/issues/1173)).
- **Severity (observed):** The first line of each inline comment is `_📐 <Category>_ | _🟡 Minor_ | _⚡ Quick win_`. The middle field is severity. "Minor" was seen with 🟡; other levels such as Major or Critical follow the same pattern but were not verified here.
- **Fixtures:** https://github.com/stablyai/orca/pull/12024 (5 inline), https://github.com/openemr/openemr/pull/13336 (1 inline), and the rate-limited PR https://github.com/hathach/agentrc/pull/598.

## 2. Greptile

- **Site:** https://www.greptile.com. **Pricing:** https://www.greptile.com/pricing. **Docs:** https://www.greptile.com/docs
- **App:** https://github.com/apps/greptile-apps (owner `greptileai`). **Login:** `greptile-apps[bot]`
- **Free terms** ([pricing](https://www.greptile.com/pricing), [OSS](https://www.greptile.com/pricing/open-source)):
  - Starter is free for 1 active developer, with 50 credits/mo and unlimited repos. A review costs 1 to 10 credits depending on tier.
  - Pro has a 14-day trial, and its credits are shared across the org.
  - OSS program: a public repo with an OSI-approved license, non-commercial. Repos with 50+ stars are auto-approved; others apply via the link on the pricing page.
- **Commands:** Comment `@greptileai` to force a review; this also works on drafts. A "Re-trigger Greptile" link sits in the footer. To disable auto review, set `"autoReview": []` (legacy: `"skipReview": "AUTOMATIC"`) ([trigger](https://www.greptile.com/docs/code-review-bot/trigger-code-review), [greptile.json](https://www.greptile.com/docs/code-review-bot/greptile-json)).
- **Config:** `greptile.json` at the repo root, read from the PR source branch. `.greptile/` takes precedence if both exist ([greptile.json](https://www.greptile.com/docs/code-review-bot/greptile-json)).
  ```json
  { "autoReview": [], "statusCommentsEnabled": false,
    "summarySection": {"included": false},
    "includeSequenceDiagram": false, "sequenceDiagramSection": {"included": false},
    "strictness": 2, "commentTypes": ["logic","syntax","style"] }
  ```
  No poem feature is documented.
- **Quota reply:** Not found in the docs or in a quick issue search.
- **Severity (observed):** Each inline comment starts with a badge image whose `alt` is `P0`/`P1`/`P2`, e.g. `<img alt="P1" src=".../badges/p1.svg">`, followed by a bold title. The summary comment has the `<!-- greptile_summary -->` marker and "Confidence Score: N/5". The config's `strictness` 1–3 is a threshold, not a label.
- **Fixtures:** https://github.com/doobidoo/mcp-memory-service/pull/2137, https://github.com/metrist38/fefw-recomp/pull/196

## 3. Ellipsis (ellipsis.dev)

- **Site:** https://www.ellipsis.dev. **Docs:** https://www.ellipsis.dev/docs (docs.ellipsis.dev 301-redirects here). **Pricing:** https://www.ellipsis.dev/docs/pricing
- **App:** https://github.com/apps/ellipsis-dev. **Login:** `ellipsis-dev[bot]` ([code-review](https://www.ellipsis.dev/docs/code-review))
- **Surprise: the product has become a general agent platform** (sessions, environments, Claude Code/Codex harnesses). Code review is now one configured "agent".
- **Free terms:** Prepaid credits, plus compute billed per CPU-hour and model tokens with a 10% platform fee. No free tier, OSS program or trial is documented ([pricing](https://www.ellipsis.dev/docs/pricing)).
- **Config:** `.ellipsis/code-review.yaml` on the default branch, with `kind: code_review`. Keys ([code-review](https://www.ellipsis.dev/docs/code-review)):
  - `pull_requests`: filters
  - `reviewers[]`: each with `claude_code` or `codex`, a `prompt` and a `model`
  - `output.on_pass`: `silent|comment|approve`
  - `output.on_fail`: `comment|request_changes`
  - `output.summary`: true or false
  - `budget.session`
- **Manual trigger and disabling auto review:** No comment command is documented. The triggers page lists a PR `on: [commented]` trigger and says `@ellipsis` mentions are configured in agent files ([triggers](https://www.ellipsis.dev/docs/agents/triggers)). Auto review is controlled with the `pull_requests` filters; no on/off switch is documented.
- **Severity:** Binary. Each comment is blocking or non-blocking, and any blocking comment fails the review ([code-review](https://www.ellipsis.dev/docs/code-review)).
- **Quota reply:** The docs say "Paid requests stop when your balance … is exhausted"; no comment text is documented.
- **Fixtures:** The recent comments look like conversational agent replies, not classic review findings. https://github.com/ashcoft/tt-rss-non-dockerize/pull/308, https://github.com/CYoJkoY/Yoko-ScriptCat-Scripts/pull/85

## 4. Graphite (AI Reviews / "Graphite Agent", formerly Diamond)

- **Site:** https://graphite.com (graphite.dev redirects here). **Pricing:** https://graphite.com/pricing. **Docs:** https://graphite.com/docs/ai-reviews
- **App:** https://github.com/apps/graphite-app (owner `withgraphite`). **Login:** `graphite-app[bot]`. This is Graphite's general app, not one dedicated to review.
- **Free terms:** Hobby is free with "Limited AI Reviews" (the cap is not stated), and Team at $40/user/mo has unlimited reviews. The trial length is not stated, and no OSS terms are given ([pricing](https://graphite.com/pricing)).
- **Commands and config:** No comment trigger and no repo config file are documented. Reviews are enabled per repo, and rules and exclusions are set in the dashboard; personal repos need the app installed on the personal account ([setup](https://graphite.com/docs/ai-reviews-setup), [customization](https://graphite.com/docs/ai-review-customization)).
- **Severity:** The docs name categories only (logic bugs, edge cases, security, performance, accidentally committed code), with no severity labels ([review comments](https://graphite.com/docs/ai-review-comments)). The observed inline comments are plain prose with no label.
- **Quota reply:** Not documented and not observed.
- **Fixtures:** https://github.com/aduthekaddu/orbit/pull/243, https://github.com/better-lyrics/composer-bridge/pull/19

## 5. CodeAnt AI

- **Site:** https://www.codeant.ai. **Pricing:** https://www.codeant.ai/pricing. **Docs:** https://docs.codeant.ai
- **App:** https://github.com/apps/codeant-ai (owner `CodeAnt-AI`). **Login:** `codeant-ai[bot]`
- **Free terms:**
  - The pricing page shows a $0 option with "Start free trial" but no stated terms ([pricing](https://www.codeant.ai/pricing)).
  - Aggregators say there is no free plan, only a trial (*third-party*: [toolradar](https://toolradar.com/tools/codeant-ai/pricing)).
  - CodeAnt's own blog says OSS projects get 100% off by arrangement with the team ([blog](https://codeant.ai/blogs/github-ai-code-review-tools-open-source)).
  - Limits are not documented.
- **Commands:** `@codeant-ai: review` re-runs a review, and `@codeant-ai ask: …` asks a question ([howToUse](https://docs.codeant.ai/pull_request/howToUse)). No way to disable auto review is documented; settings live in the dashboard at app.codeant.ai.
- **Config:** Mostly in the dashboard ([code_review](https://docs.codeant.ai/pull_request/features/code_review.md)). There is an org-wide `.codeant/` repo config ([global_repo_config](https://docs.codeant.ai/pull_request/customize/global_repo_config.md)), and PR description settings are at [description](https://docs.codeant.ai/pull_request/description.md). No poem or diagram keys are documented.
- **Severity:** Critical, High, Medium and Low in the docs ([code_review](https://docs.codeant.ai/pull_request/features/code_review.md)). The observed line is `**Assessment:** 🟠 \`Major\` · 🔁 \`Occurrence: Sometimes\` · 🏷️ \`Incorrect condition logic\``. Note that "Major" appears in live output although the docs do not list it. The status comment is titled "CodeAnt Review Status".
- **Quota reply:** Not found.
- **Fixtures:** https://github.com/Convospanai-outreach/fullstack/pull/1047 (12 inline), https://github.com/jsaluja09ufl/CEN3031_Group_Project/pull/15

## 6. Qodo (Qodo Merge / PR-Agent, now "Qodo Code Review")

- **Site:** https://www.qodo.ai. **Pricing:** https://www.qodo.ai/pricing/. **Docs:** https://docs.qodo.ai/code-review (qodo-merge-docs.qodo.ai redirects here)
- **App:** https://github.com/apps/qodo-code-review (owner `qodo-ai`). **Login:** `qodo-code-review[bot]`. The legacy `qodo-merge-pro` slug no longer exists.
- **Free terms:**
  - "We don't offer a permanent free tier." The 14-day trial has no card requirement and unlimited reviews. After that, reviews draw on a shared monthly credit pool per workspace ([pricing](https://www.qodo.ai/pricing/)).
  - OSS program: a public repo with 100+ stars that is actively maintained; install from the Marketplace. It covers core PR review, not Rules or PR History ([OSS](https://docs.qodo.ai/open-source-program)).
  - The old "75 PR feedbacks/month per org" free quota appears only on legacy pages.
  - The self-hostable PR-Agent is now community-run at https://github.com/The-PR-Agent/pr-agent.
- **Commands:** `/agentic_review`; a 👀 reaction acknowledges it. To disable auto review, remove the command from `pr_commands` under `[github_app]`, or set the trigger to "Manual only" ([use-qodo-in-prs](https://docs.qodo.ai/code-review/use-qodo-in-prs.md)). The full command list is at [the command reference](https://docs.qodo.ai/code-review/pr-command-and-interaction-reference.md).
- **Config:** `.pr_agent.toml`.
  ```toml
  [github_app]
  pr_commands = []            # drop /agentic_review and /agentic_describe
  [review_agent]
  inline_comments_severity_threshold = 1
  ```
  No explicit key for diagrams or summaries is documented beyond `pr_commands` (see [reduce-review-noise](https://docs.qodo.ai/code-review/reduce-review-noise.md)).
- **Severity:** High, Medium and Low ([severity-thresholds](https://docs.qodo.ai/code-review/severity-thresholds.md)). The observed format has a badge such as `Review_recommended`, then `1. <title> <code>🐞 Bug</code> <code>≡ Correctness</code>`.
- **Quota reply (observed, very common):**
  - `<!-- qodo:billing-blocked -->` **ⓘ Qodo reviews are paused because your trial has ended.** … ([eBoot#214](https://github.com/embeddedos-org/eBoot/pull/214))
  - `### Qodo reviews are paused for this user.` ([isometrik-ai/...#354](https://github.com/isometrik-ai/ats-home-craft-python-service/pull/354)), linked to [subscription-plans](https://docs.qodo.ai/subscription-plans#what-you%E2%80%99ll-see-when-reviews-are-paused)
- **Fixtures:** https://github.com/joefeser/tracemap/pull/577, https://github.com/The-Running-Dev/SubZeroDev.GameEngine/pull/96

## 7. devlo (devlo.ai)

- **Site:** https://devlo.ai. **Docs:** https://docs.devlo.ai. **Plans:** https://docs.devlo.ai/account/plans/
- **App:** https://github.com/apps/devloai (owner `devlo-org`). **Login:** `devloai[bot]` ([docs](https://docs.devlo.ai/))
- **Free terms:**
  - The Free plan is $0 with 500 credits/mo and 2 projects. Paid plans: Builder $19, Pro $39, Startup $199. Credits are $1 per 100 ([devlo.ai](https://devlo.ai/)).
  - Reviews spend the org's credits. A new org uses the installer's personal plan until it gets its own ([plans](https://docs.devlo.ai/account/plans/)).
  - The cost of a review varies with size and model. No OSS terms are given.
- **Commands:** `/review` as the whole comment ([commands](https://docs.devlo.ai/reference/commands/)). To make reviews manual only, remove the "New pull request" trigger under Automations > Code Reviewer in the dashboard, or set it to Paused ([running-reviews](https://docs.devlo.ai/code-review/running-reviews/)).
- **Config:** No repo file is documented; configuration is in the dashboard.
- **Severity:** Not documented. Observed inline comments are plain prose.
- **Quota reply (observed):** `Unable to trigger custom agent "Code Reviewer". devlo is paused for this organization because it is out of credits. An admin can upgrade the plan or buy credits on the [plan page](...)` ([mjcumming/pywiim#51](https://github.com/mjcumming/pywiim/pull/51))
- **Fixtures:** https://github.com/g4vin001/RestaurantApp/pull/1, https://github.com/Heisdawrld/Tactico/pull/4

## 8. CodeReviewBot.AI

- **Site and pricing:** https://codereviewbot.ai (operator: "Accelerating Progress Inc."). **Docs:** none linked from the site.
- **App:** https://github.com/apps/codereviewbot-ai. **Login:** `codereviewbot-ai[bot]`
- **Free terms:** Hobby is $0 and "100% Free for public OSS repos," plus 10 reviews/mo on private personal repos. Team is $25/mo with a 30-day trial (the FAQ says 30 days or 40 reviews) ([site](https://codereviewbot.ai/)). Rate-limit scope is not stated.
- **Commands and config:** Reviews run when a PR is created. No comment command and no config file are documented; options are set in the dashboard ([site](https://codereviewbot.ai/)).
- **Severity:** Not documented. Observed comments are prose plus GitHub ```` ```suggestion ```` blocks.
- **Quota/skip reply (observed):** `🤖 Review skipped: reviews for bot-created pull requests are not allowed on free accounts. Upgrade to a paid plan to enable bot reviews.` ([chirag127/sri-ganesh-bazaar#6](https://github.com/chirag127/sri-ganesh-bazaar/pull/6)). **This matters if the router's PRs are opened by a bot account.**
- **Fixtures:** https://github.com/micha-sky/kalendarski/pull/1 (inline finding), https://github.com/chirag127/sri-ganesh-bazaar/pull/6 (skip message). Public usage is sparse.
