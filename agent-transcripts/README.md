# Agent transcripts

This submission was built with Claude acting as the coding agent, directed interactively by the
candidate. Per the assignment's "Use AI tools thoughtfully" note, this folder documents what the
agent did, including failed attempts and corrections, rather than just the final diff.

`session-log.md` is a condensed, secrets-scrubbed narrative of the build session: the order
operations happened in, what was verified by actually running code (not just written), and the
mistakes hit along the way and how they were fixed. It intentionally keeps the technical detail
(exact commands, file names, error messages) so an evaluator can see the actual working process,
not a cleaned-up retelling.

No API keys, tokens, or credentials appear in this log — none were used during the build; all
verification was done with a fake/mocked LLM provider (see `test_chat_api.py`) and read-only
access to the public transcripts repository.
