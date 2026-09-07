Output assets/agentmeld-demo.gif

Set Theme "Catppuccin Mocha"
Set FontSize 16
Set Width 1200
Set Height 760
Set TypingSpeed 55ms

Type "export PATH=/Users/vampiremac/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
Enter
Sleep 700ms

Type "rm -rf /tmp/agentmeld-demo && mkdir -p /tmp/agentmeld-demo"
Enter
Type "cd /tmp/agentmeld-demo"
Enter
Sleep 500ms

Type "mkdir -p .github .cursor/rules"
Enter
Type "printf '# Working here\\n\\nRun tests with pytest.\\n' > CLAUDE.md"
Enter
Type "printf '# Copilot instructions\\n\\nUse concise commits.\\n' > .github/copilot-instructions.md"
Enter
Type "cat > .cursor/rules/testing.mdc <<'EOF'"
Enter
Type "---"
Enter
Type "description: Testing guidance"
Enter
Type "globs:"
Enter
Type "  - tests/**"
Enter
Type "alwaysApply: false"
Enter
Type "---"
Enter
Type "Use fixtures, not setUp."
Enter
Type "EOF"
Enter
Sleep 500ms

Type "git init -q && git config user.email demo@example.com && git config user.name demo && git add -A && git commit -qm 'init'"
Enter
Sleep 800ms

Type "agentmeld detect"
Enter
Sleep 2s

Type "agentmeld init --dry-run"
Enter
Sleep 3s

Type "agentmeld init"
Enter
Sleep 3s

Type "tree -a .ai | head -n 40"
Enter
Sleep 3s
