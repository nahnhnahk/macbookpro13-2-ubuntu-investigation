# Keeping the history current

This repository is the durable public investigation record. Git records subsequent changes; no background process automatically copies private machine logs or pushes new experiments.

For each future investigation session:

1. Pull the current main branch and read `CURRENT-STATE.md` plus the latest timeline entries.
2. Record the exact model, kernel/source versions and relevant configuration before changing anything.
3. Save a new uniquely named evidence directory. Preserve original results, including failures. Keep raw private captures locally and create a reviewed, sanitized public subset.
4. Distinguish observations, inferences, unsuccessful hypotheses and confirmed repairs. Include actual sleep time, wake trigger, controller side, return values and network validation where relevant.
5. Update current state, validation, open questions and upgrade/rollback instructions when behavior changes. Append a dated timeline entry; do not rewrite earlier observations to make them appear successful.
6. Run source tests, the publication checker and JSON integrity checks. Refresh `SNAPSHOT-SHA256SUMS.json` using the checker’s `--write-manifest` option and review the resulting Git diff.
7. Commit the coherent change with its evidence, then push main or open a review branch as appropriate. Each publication should be authorized for its intended scope.

Example local checks from this repository root:

```sh
python3 -m unittest discover -s kernel-test/t1-upgrade -p 'test_*.py'
(cd kernel-test && python3 -m unittest test_grub_selection test_suspend_wait test_sleep_duration test_package_permissions)
python3 tools/check-publication.py --write-manifest
python3 tools/check-publication.py
```

The directory-permission repair tests exercise an API whose production owner/group default is root. On a system where the test user's UID and GID differ, run that suite in an isolated root container or as an administrator after reviewing the tests. CI uses an isolated container. The tests mock hardware/firmware operations; never substitute real suspend for a unit test.

Record kernel upgrades explicitly. The selected old kernel's boot-default preservation is not automatic security-update coverage. Review, rebuild/test or validate a suitable stock replacement before promotion.
