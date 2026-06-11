# Aurora DDR AI Rules

## Branch Safety
1. Never modify the main branch.
2. Work only on the currently checked out branch.
3. Do not execute git push.
4. Do not execute force push.

## Code Changes
5. Explain the implementation plan before making changes.
6. List files that will be modified.
7. Prefer additive changes over refactoring.
8. Do not remove existing functionality unless explicitly requested.

## DDR Project Rules
9. All collectors must fail gracefully.
10. Any new report section must have a matching collector.
11. Do not hardcode database names or connection details.
12. Preserve backward compatibility.

## Review Process
13. Show a summary of changes before implementation.
14. Ask for confirmation before modifying code.
15. Do not modify more files than necessary.