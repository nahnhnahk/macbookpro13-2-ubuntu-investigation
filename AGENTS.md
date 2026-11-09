# Investigation archive maintenance

- Read `docs/CURRENT-STATE.md` first. Historical notes describe superseded states as well as the final repair.
- Preserve failures and uncertainty; do not count the old duration-unchecked reports as successful sleep validation.
- Record future findings in dated timeline entries and new sanitized evidence directories. Update the current state and remaining work together.
- This is a source/evidence archive. Kernel packages, runtime binaries, credentials, private firmware/machine dumps and full private journals must stay outside Git.
- Keep copyright and source attribution. Public placeholder identities must remain synthetic. Review copied logs and paths before publication.
- Source inspection and unit tests must not execute firmware methods, suspend, reboot, reload live drivers or modify installed configuration.
- Hardware validation and installation require their actual authorized machine context. Do not infer authorization from an old historical instruction.
- Run the documented unit tests and `tools/check-publication.py`; refresh the snapshot hash index for intended edits.
- Git retains future changes. Do not fabricate earlier commit dates or rewrite successful results into failed historical trials.
