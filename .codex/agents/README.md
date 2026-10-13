# Codex project agents

No .claude/agents/ directory or agent Markdown files existed in this checkout
when the adapter was created. No agent definitions have been converted or
invented. This README is documentation, not a discoverable agent.

For a Claude agent that Codex should spawn, create a matching
.codex/agents/<name>.toml. Use a unique name and a concise description; put the
Markdown instruction body into developer_instructions. For example:

```toml
name = "example_reviewer"
description = "Reviews the requested app changes and reports findings."
sandbox_mode = "read-only"
developer_instructions = """
Read AGENTS.md and CLAUDE.md before reviewing the assigned scope.
Report concrete correctness problems with file references.
Do not modify files.
"""
```

The example is not installed. Preserve the source agent's role and constraints
when converting an actual agent. Review Claude front matter such as model,
tools, and permissions rather than copying those values verbatim. Translate
Claude-only tool references to available Codex capabilities. Omit model
overrides unless needed, allowing inheritance. Keep sandbox restrictions suited
to the role; never add credentials or broaden access just to match Claude.
Keep both agent versions aligned and link long shared references in docs/,
references/, or templates/ rather than copying them into every definition.

Custom-agent support depends on the installed Codex version and client.
Verify discovery there before relying on delegation.

Format reference: https://learn.chatgpt.com/docs/agent-configuration/subagents
