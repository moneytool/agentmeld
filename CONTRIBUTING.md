# Contributing

## Adding support for an AI tool

Most of the time this needs **no Python**. Adapters are declarative TOML in
`src/agentmeld/registry/adapters/`. Copy the closest existing one and edit it.

```toml
id = "yourtool"
name = "Your Tool"
confidence = "verified"          # see below -- be honest
docs = "https://link-to-the-page-that-proves-these-paths"
detect = [".yourtool/"]          # what proves the tool is in use

[kinds.rule]
target = ".yourtool/rules/{slug}.md"
strategy = "generate"            # link | generate | merge | aggregate
transformer = "markdown"
[kinds.rule.frontmatter]
globs = "appliesTo"              # canonical key -> vendor key
always = "appliesTo!**"          # if truthy, set appliesTo to "**"
description = "__drop__"         # vendor has no equivalent
```

### The confidence field is not decoration

`confidence = "verified"` means **you read the vendor's own documentation and the
path and frontmatter keys are stated there**. A blog post, an LLM answer, or "I'm
fairly sure" is `unverified`, which keeps the adapter out of the default sync.

This matters because agentmeld *moves people's files*. A wrong path does not
produce a harmless no-op; it scatters files into a directory the tool never reads
and quietly loses the user's context. Please link the doc page in `docs`.

Per-kind overrides are allowed and encouraged — a tool's main instruction file is
often documented while its skills directory is not:

```toml
[kinds.agent]
confidence = "unverified"
note = "Seen in community docs; not in the vendor's own documentation."
```

### Picking a strategy

| Strategy | Use when |
|---|---|
| `link` | the vendor reads the canonical bytes unchanged |
| `generate` | frontmatter keys or the file format differ |
| `merge` | the target is shared config the user also edits (MCP, settings.json) |
| `aggregate` | the tool has one instruction file and no rule mechanism |

Prefer `link` whenever it is truthful — it is the whole point of the project.
Never use `link` if the vendor would misread the canonical frontmatter.

## Running the tests

```bash
uv sync
uv run pytest
```

Please make sure new behaviour is covered on Windows too, or explain why it
cannot be. The symlink fallback is only real because CI exercises it.

## Things that need to stay true

- `sync` twice in a row produces byte-identical output.
- Nothing is ever written inside the canonical tree.
- A file agentmeld did not create is never overwritten; it becomes a conflict.
- `watch` reaches quiescence — syncing writes into the directories it watches, so
  a change to the loop guards needs a test proving it settles.
