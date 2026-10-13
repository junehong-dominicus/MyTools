# Codex project skills

No .claude/skills/ directory or project SKILL.md files existed in this checkout
when the adapter was created. No skills have been copied or invented.

When a Claude skill should also be available to Codex, copy the whole
.claude/skills/<name>/ folder to .agents/skills/<name>/. Keep SKILL.md, scripts,
references, templates, and assets together. SKILL.md must have YAML front matter
with name and description. Review Claude-specific tool names and paths for
Codex compatibility, and document any adapter differences in the copied skill.
Update both versions when the workflow changes; put substantial shared
knowledge in docs/, references/, or templates/ and reference it from both.

Do not copy credentials, local settings, environments, or session state.
Do not place project skills in .codex/skills/.

Discovery reference: https://learn.chatgpt.com/docs/build-skills
