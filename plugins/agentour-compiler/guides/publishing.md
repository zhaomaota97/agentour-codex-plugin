# Publishing

Require explicit `AGENTOUR_URL`; discover models through `${AGENTOUR_URL}/v1/models`. Require `AGENTOUR_TOKEN` only when publishing.

Prefer asynchronous publication:

```bash
python3 "${CODEX_PLUGIN_ROOT}/scripts/agentour_api.py" publish-async packages/<agent-id>
```

Before uploading, show the destination host, Agent ID, version, visibility, fidelity grade, and unsupported capabilities. Never publish to a remote platform without authorization.

Run `remote-build` only after final confirmation. Cached responses are successful evidence and
do not consume quota. Treat `429` as a quota wait condition, not as a retry invitation. Repair
deterministic structured Gate failures before resubmitting, and use `cancel-build <job-id>` for a
superseded Build.
