---
description: How to mark adapter confidence honestly
globs:
  - src/agentmeld/registry/adapters/*.toml
---
`confidence = "verified"` means the path and frontmatter keys are stated in the
vendor's own documentation, and `docs` links the page that proves it. Anything
learned from a blog post, a search summary, or recollection is `unverified`, and
stays out of the default sync.

A wrong path is not a harmless no-op: it scatters a user's context into a
directory the tool never reads.
