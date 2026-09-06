<!-- agentmeld:generated source=.ai/instructions.md hash=46e7d9865747 -- edit the source, not this file -->

# agentmeld

One canonical copy of your AI context in `.ai/`, mirrored into every AI tool's
own location — a real symlink where the formats agree, a small generated file
where they genuinely differ.

## Working here

- `uv sync` then `uv run pytest`. The suite must pass on Python 3.9 as well as
  current versions: run `uv run --python 3.9 --with pytest --with pyyaml --with
  tomli python -m pytest -q` before claiming compatibility.
- Adapters are **data**, in `src/agentmeld/registry/adapters/*.toml`. Adding a
  tool should not require Python.
- This tool moves people's files. Prefer refusing to act over acting on a guess.

## Invariants that must not break

- `sync` twice produces byte-identical output.
- Nothing is ever written inside the canonical tree.
- A file agentmeld did not create is never overwritten; it becomes a conflict.
- `watch` reaches quiescence, because syncing writes into the directories it
  watches.

## Rules

### adapter-confidence

How to mark adapter confidence honestly

_Applies to: src/agentmeld/registry/adapters/*.toml._

`confidence = "verified"` means the path and frontmatter keys are stated in the
vendor's own documentation, and `docs` links the page that proves it. Anything
learned from a blog post, a search summary, or recollection is `unverified`, and
stays out of the default sync.

A wrong path is not a harmless no-op: it scatters a user's context into a
directory the tool never reads.
