# Evidence index

`build/` preserves the stock-to-test configuration differences, source style/optional-operations checks, external-driver header-build metadata, and the original local artifact manifest. The referenced binaries/packages are not distributed in this repository.

`validation/` contains selected redacted captures:

| Capture | Meaning |
|---|---|
| `validation-6lgmwrhh` | Historical verifier false positive: no measured-duration check; never use as a long-sleep pass |
| `validation-jpzj_1kb` | Measured early wake, 3.196 s; RTC still pending; lid/GPE evidence retained |
| `validation-5yac3kyp` | Successful short closed-lid comparison, 99.261 s |
| `validation-3mtfzxvb` | Successful extended closed-lid comparison, 9908.864 s |
| `validation-n689igio` | Successful opposite-controller comparison, 104.941 s |

`audio-2026-11-08/` records the internal-speaker diagnosis, the failed DKMS build, the rootless build tests and before/after kernel-log excerpts.

Original report semantics are preserved. A `result.json` with `suspend_requested: null` is a post-wake health check; its independent comparison snapshots and journals establish sleep duration. A `manual-validation-summary.json` is derived from those raw preserved fields. Kernel excerpts were limited to recovery-related events, and broad host snapshots were omitted or narrowed.

`docs/VALIDATION.md` explains timing, qualification, deduplication and limitations. Raw private originals remain in the machine-local workspace.
