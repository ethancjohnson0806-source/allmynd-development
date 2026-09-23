# Contributing

ALL MY'ND is being developed as a careful, testable research codebase. Keep changes narrow and preserve provenance.

## Before changing behavior

Read the relevant source and the matching sections of `ALLMYND_CHANGELOG.md`. Treat historical claims as leads to verify, not as guarantees. Do not run a historical `fix_*.py` script unless you understand its target and have a backup of the working tree.

## Every behavior change should include

1. A focused regression test or a documented reason a test cannot be added.
2. A changelog entry describing what was verified and how.
3. No runtime state, credentials, phone data, or generated audio in the commit.
4. A clear note when behavior is experimental, nondeterministic, or dependent on Termux APIs.

## Bridge changes

Keep the public bridge narrow. New remote operations require an explicit threat model, authentication design, input and output limits, timeout behavior, and negative tests before they are enabled.

## Local verification

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```
