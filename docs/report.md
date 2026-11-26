# Code review agent muxing: what we learned

2026-11-26

## Summary

Seven AI code review bots can be run for free or nearly free on a public repo, each
started only by an explicit trigger. We tested nine services on 2026-11-25 and 26;
seven work, two were dropped. The muxer (review_mux) will decide which bots review
each PR and merge their findings into one review.

The main lesson: most bots review every PR and every push by default, and that burns
credit. Each one has to be switched to trigger-only, often through a setting that
exists only in its web dashboard.

## Results

Every working bot stays silent on new PRs and pushes, and reviews when triggered.

| Bot | Trigger | Free terms | Cost seen | Result |
|---|---|---|---|---|
| Ellipsis | Comment `@ellipsis review this PR for bugs` | $100 one-time credit for a new organization | $0.20 for an 8-line PR (Opus 5.5) | Works |
| devlo | Comment `/devlo-review` | 500 credits a month | About 6 credits a review | Works |
| CodeRabbit | Comment `@coderabbitai review` | Free plan, 10 reviews an hour; trial covers overage | Free | Works |
| Greptile | Comment `@greptileai` | Free plan credits, which expire | Credits | Works after selecting the Free plan |
| CodeAnt | Comment `@codeant-ai: review` | Says free for open source | Free | Works |
| Qodo | Comment `/agentic_review` | 14-day trial | Trial | Works once enabled for the repo |
| Graphite | `/graphite-review` in the PR description | Hobby plan, limited reviews | Free | Works; reports through a check run |
| CodeReviewBot.AI | None (reviews on PR open) | Free for open source | — | Dropped: never responded |
| GitHub Copilot | Request Copilot as reviewer | Needs a paid plan | — | Dropped: Copilot Free ignores it |

## Lessons

- **Automatic review is the default, and it burns credit.** devlo used 18 of its 500
  credits in minutes by reviewing every push. Ellipsis reviewed and approved every
  new PR.
- **Key settings live only in dashboards.** devlo's trigger is under Automations →
  Code Reviewer → Event Trigger. Ellipsis's automatic reviewer ignores repo config
  files and can't be set to no repos, so we pointed it at a dead repo. CodeAnt, Qodo
  and Graphite were also fixed in their dashboards.
- **Off switches can block triggers too.** Qodo ignored its command until it was
  switched on for the repo. Graphite ignored our PRs until set to review all
  committers.
- **Pricing pages don't match reality.** devlo, Ellipsis and CodeAnt were more
  generous than third-party listings said. CodeRabbit's "free for open source" is a
  rate-limited plan. Greptile had no credits until the Free plan was selected.
- **Bot approvals are meaningless.** Ellipsis approved a PR in which it had just
  found a bug. Approvals must never count toward merging.
- **Bots report differently.** Most post comments; Graphite uses a check run. Several
  report their own cost or quota (Ellipsis "$0.20", CodeRabbit "9 remain"), which the
  muxer can read.
- **Test on a throwaway account first.** We dry-ran on a spare account, so the real
  setup can follow written steps without wasting trials.

## Routing

For each PR, the muxer picks the bots that give the most useful review for what they
cost. It weighs four things:

- **Quality:** how often a bot's comments lead to fixes. It starts as a guess
  (Ellipsis on Opus 5.5 highest; devlo good) and is then measured.
- **Cost:** dollars for Ellipsis, credits for devlo and Greptile, nothing for CodeAnt
  and CodeRabbit within its limit.
- **Expiry:** credits about to expire cost almost nothing to use, so Greptile is
  spent first.
- **Stakes:** a big or risky PR justifies Ellipsis; a small one gets only free and
  expiring bots.

The muxer then collects every bot's findings, merges duplicates (same file, diff side
and nearby lines), and posts one check run. Bot approvals are recorded as a signal
only.

## Next steps

- [ ] Check that Qodo doesn't auto-review new PRs now that it is on for the repo
- [ ] Opt out of CodeRabbit's usage-based reviews when the trial ends
- [ ] Record Greptile's credit amount and expiry date
- [ ] Build the muxer: collect, dedupe, route, ledger, merged check run
- [ ] Repeat the setup on the real account using the written steps

Setup steps for every bot: [setup.md](setup.md).
