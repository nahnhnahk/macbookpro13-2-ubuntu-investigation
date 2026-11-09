# Public snapshot handling

The local source and capture files were reviewed before the public repository was created. The source workspace and installed configuration remain separate from this archive.

## Replacements

- Home paths use `/home/example/macbookpro-ubuntu`.
- The example Ethernet interface is `enx020000000001`.
- IPv4 addresses from the private LAN use documentation prefix `192.0.2.0/24`; these are examples, not suggested LAN settings.
- MACs use synthetic locally administered `02:00:00:00:00:xx` examples. Their OUIs must not be used to repeat the original vendor lookup. The LG vendor finding was made against the original, omitted address.
- DHCP client identity, actual host name, machine/profile UUIDs, boot IDs and printed kernel object addresses are redacted or consistently replaced.
- Public upstream author attribution and original license notices are retained.

Full kernel/build trees, packages, runtime acpidbg, private signing keys, credentials, full firmware dumps, complete system journals and application logs are excluded. Selected kernel and systemd excerpts preserve only relevant recovery events. Timing baselines retain clocks and counters while omitting broad host snapshots.

`PUBLIC-SNAPSHOT.json` records each copied source file's original and public hashes, including deliberate substitutions. `SNAPSHOT-SHA256SUMS.json` verifies the committed snapshot's file contents. Git objects and generated caches are excluded from that index.

The privacy checker rejects actual LAN addresses, unsanitized home paths, MAC-derived interface names, credential-like token/key formats, unwanted binary/build artifacts and inconsistent snapshot hashes. This complements the manual review; it is not a general secret-detection guarantee.
