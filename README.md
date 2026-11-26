# review_mux

Route pull requests across AI review bots, and merge their findings into one
review. What we learned setting the bots up: [docs/report.md](docs/report.md);
how each is set up: [docs/setup.md](docs/setup.md).

## What it does

For each head commit of a pull request it reviews:

1. **Routes**: picks the bots worth asking (`providers.yml`). Free bots and
   credits about to expire first; the best paid bot only for big changes
   (300+ lines) or the label `review:deep`. A bot that ran out of quota is
   left alone for 6 hours.
2. **Triggers** each one, as the account that installed it (a comment, or for
   Graphite a line in the description, taken out afterwards).
3. **Waits** for each bot's own "done" signal, its out-of-quota reply, or its
   timeout.
4. **Reports** once: a commit status `review_mux` on the head, and one PR
   comment (edited in place) with every finding merged across bots.
   - `success`: at least one bot reviewed and nobody found anything.
   - `failure`: an inline finding, or a summary that a bot's rules count as one
     (Greptile confidence 3 or less, Qodo medium or worse, CodeAnt medium risk or
     worse, Ellipsis anything but "no bugs").
   - `error`: no routed bot gave a review.

   Bot approvals count for nothing.

Everything it does and sees, including spend (Ellipsis's `$`, CodeRabbit's
"N remain"), goes into an append-only ledger, `review_mux.jsonl`, so a
restart resumes and a review is never paid for twice.

## Running it

    uv run --with pyyaml python -m review_mux route OWNER/REPO PR        # who it would ask
    uv run --with pyyaml python -m review_mux review OWNER/REPO PR --wait
    uv run --with pyyaml python -m review_mux watch OWNER/REPO --author LOGIN --report-as ACCOUNT

`watch` must be told which pull requests to review (`--author`, `--label` or
`--all`), since every review spends something. Tokens: each bot's
`trigger_as` account needs `GH_TOKEN_<ACCOUNT>` or a `gh auth login` for it.

Tests: `uv run --with pyyaml --with pytest pytest -q`.
