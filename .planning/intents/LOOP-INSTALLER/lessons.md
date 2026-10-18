# Distribution lessons — reviewable, not auto-promoted rules

| Observed failure | Actual evidence | Reusable check |
|---|---|---|
| Skills omitted by npm wildcard packaging | initial local package smoke failed; tarball assertions now count all9 Skills | Test the shipped tarball, not only source imports |
| GitFetcher Arborist failure | run39099490690 / job117592645675 | Execute the exact public installation command |
| Windows UTF-8 root / permissions mismatch | run39099490690 / jobs117592645748 and117592645849 | Test non-ASCII consumer roots and repeat installation on Windows |
| Added Claude omitted existing Codex native files | run39099490690 / job117592645768 | Test runtime addition plus old-runtime doctor and relocation |

These observations improved existing package/CI tests. No new global Rule was self-approved. A general distribution Skill remains a proposal until independently reviewed; model quality and unrelated business assumptions are not inferred from these incidents.
