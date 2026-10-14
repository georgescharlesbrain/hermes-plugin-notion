# Maintain the Notion plugin

The plugin repository owns its two skills, references and workspace CLI wrapper.
Profiles share code but not credentials, trust, replay state or sessions.

Before implementation, read the host's Hermes development instructions.
Work in an isolated checkout as the Hermes owner, not in the live plugin tree.
Use the public plugin API and plugin repository rather than changing Hermes core.

1. Read the exact Asana task and existing subtasks.
2. Check the installed branch, HEAD and cleanliness.
3. Preserve unknown operational state and profile-specific permissions.
4. Implement and test the candidate in an isolated checkout.
5. Independently review relevant behavior and record residual limits.
6. Push the candidate. Verify the remote commit.
7. Install only after checking live ancestry and cleanliness; use a fast-forward.
8. Coordinate an approved gateway reload after all served agents are idle.
9. Check both profile listeners, actual vendor events and exact reply readback.

Use plugin tests, not the full Hermes core suite, for a plugin change.
Check profile isolation, author denial, foreign integration IDs, bot suppression,
FYI/thanks filtering, replay, concurrent reply budgets and process persistence.
Selected-text context is not proof of the exact highlighted substring.
Stop does not guarantee cancellation of a running model.

Before root configuration changes, preserve the configuration and identify
rollback. Validate before restarting. Obtain the required approval for sudo
and system-level changes. Use the admin account for approved root operations.

Keep the parent description short. Each subtask carries its own result,
evidence, remaining work and explicit open questions. Read back every Asana
write. Distinguish DONE artifacts from PARTLY verification gaps and OPEN work.
Only the human completes a task.

Before retiring old standalone skills, verify the replacement is registered and
usable. Preserve recoverable source copies and references. Disable the old
builtin name without opting out of every bundled skill. A core update must not
silently restore the retired guidance as active.
