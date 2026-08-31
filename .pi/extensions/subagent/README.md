# Project-local subagent extension

Agent definitions can load their own skills and extensions without exposing those resources to other subagents.

## Per-agent resources

Add optional `skills` and `extensions` arrays to an agent's frontmatter:

```markdown
---
name: frontend
description: Frontend implementation with project design guidance
skills:
  - ../skills/design/SKILL.md
  - ~/.pi/agent/skills/accessibility/SKILL.md
extensions:
  - ../extensions/browser-tools.ts
  - npm:@example/pi-design-tools@1.2.3
---

Implement frontend work and follow the loaded design guidance.
```

Local relative paths are resolved from the agent definition file (following agent-file symlinks). Absolute paths, `~/...` paths, and `file://` URLs are also supported. Extension entries may additionally use Pi-compatible package sources such as `npm:`, `git:`, `https:`, or `ssh:`. Prefer pinned package versions and Git revisions for reproducible agents.

Each child process starts with normal skill and extension discovery disabled, then receives the resources declared by that agent. Parallel tasks and chain steps therefore remain independent. Remote extension packages are materialized in a unique temporary directory per subagent; only their extension entries are forwarded to the child, and the directory is removed when that child exits.

If an agent sets `tools`, that field remains a complete allowlist; include the names of any tools supplied by its extensions.

> Extensions and extension packages execute with full system permissions. Only reference trusted code and packages. An untrusted project-local agent cannot load extensions in a headless run; approve the project first.
