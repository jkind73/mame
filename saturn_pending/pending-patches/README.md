# Unpushed commits (GitHub token outages)

Sandbox recycles have already cost one set of local commits, and the GitHub
token has expired mid-session twice, so any commit that cannot be pushed is
also exported here as a `git format-patch` file.

Apply from the branch tip it was taken from:

    git fetch origin arena/01a09f50-mame
    git am < saturn_pending/pending-patches/0001-*.patch

| patch | base (must be the branch tip) | content |
| --- | --- | --- |
| `0001-snd01-interrupt-chain.patch` | `71008a39` | SND-01: the sound 68000's level 6 autovector interrupt chain is measured and asserted (fixes the fixture bug that produced the earlier "open finding"), refreshed four-profile evidence, CI expectation `cases=49` |
