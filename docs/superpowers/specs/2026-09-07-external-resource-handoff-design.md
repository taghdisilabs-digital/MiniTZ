# External Resource Handoff Design

## Goal
Make customer-resource use fail-closed and lossless: the first customer waits for a verified Biella checkpoint, Biella sleeps without losing task/worktree/session continuity, overlapping customers share that sleep lease, and the last customer release restores exactly the pre-customer Biella service state.

## Authority and isolation
Biella remains the only authority over Biella task/session/runtime state. The external sandbox broker never reads or mounts Biella source, runtime, credentials, project memory, or customer data into Biella. It may call fixed root-owned systemd handoff actions only. Customer learning crosses the firewall only as records accepted by the existing coding-only LessonSanitizer and then revalidated by the Biella-side importer as project-neutral candidate evidence.

## Checkpoint and sleep
A root-owned Biella handoff helper records: Git HEAD/tree, current task, runtime/task-memory/projection digests, dirty-worktree fingerprint, and exact active/enabled states of production/Ollama/Qwen. If production is active, it writes a cooperative pause request and waits for the runner to acknowledge at a no-child safe boundary. After acknowledgement it stops and temporarily disables protected services. If Biella was already asleep, the checkpoint records that state unchanged.

## Resume
The last customer release invokes the root-owned resume action. Resume refuses while any `psb-*` customer container is running, verifies Git source alignment and the checkpointed dirty-worktree fingerprint, restores each protected service's exact prior enablement/active state, and archives the released checkpoint. Owner-requested sleep therefore remains sleep; previously active Biella resumes automatically.

## Customer lifecycle
The broker acquires the host lifecycle only before starting the first running customer. Subsequent customers do not re-checkpoint or wake/sleep Biella. On stop/finish/block, it stops the customer first, then resumes Biella only when no customer remains. A background reconciler repairs crash/reboot cases by releasing an orphaned host lease when no customer container remains. Customer containers use `restart=unless-stopped` so an active customer survives Docker/host restart while manually stopped work remains stopped.

## Blocked/finished experience sharing
Stop accepts `finished` or `blocked` and an optional list of lesson records. Records are passed through LessonSanitizer; rejected customer-specific/visual/source/path/URL content never crosses the firewall. Accepted records are written to a fixed broker handoff file and imported by the Biella helper into a project-neutral candidate inbox keyed by SHA-256. They are not automatically promoted into project authority or task memory.

## Routing recovery
Catalog-discovered `gpt-reserve` is an eligible strong recovery route. An account usage error cools only the model that produced the observed limit; independently cataloged routes remain eligible. No quota/balance probing is introduced. Stale cooldown entries are pruned when their model is no longer meant to share a failed model's cooldown.

## Completion evidence
Required proof: red/green regression tests for every new boundary; full Biella controller tests; full broker tests and host acceptance where safe; exact installed-source readback; live first/last-customer lifecycle simulation using synthetic/non-destructive service state; GitHub readback for Biella commits; preserved D03 dirty-byte digests; no customer identifiers/content in the Biella lesson inbox.
