# Installer validation — 0.2.0

Validated implementation commit: `093458821ec5ab2f04b1891fa8a5ac26779e3023`.
Verified source tree: `aa36ef29a0ab03e2b72896f137d405bdaffd6760`.

GitHub distribution run: https://github.com/hvritual/loop/actions/runs/39100387213
All eight install/compatibility jobs and source export passed. Linux, macOS, Windows exercised the actual npm tarball offline. Linux exercised Codex, Claude and OpenCode official installers; Windows additionally exercised Codex native setup. Codex Linux also added Claude to the same project and moved/reinstalled the workspace. The GitHub archive/npx entry was executed independently in a consumer directory.

GitHub quality run: https://github.com/hvritual/loop/actions/runs/39100387242
Contracts and three legacy bootstrap adapters passed. Local full suite: 112 tests, including 46 installer/regression cases; framework lint: 12 rules / 9 skills; actual npm pack contains 37 files and all 9 Skills. Native tests do not log in or call a model.

Failures were repaired, not waived: the initial npm files glob omitted Skills; npm GitFetcher failed to pack Git references; Windows Git root decoding used the wrong codec; adding a runtime dropped prior native files; Windows chmod/stat differences changed the ownership manifest. The corrected jobs retain the original assertions. Failed evidence remains in run 39099490690.

The receipt under `.planning/intents/LOOP-INSTALLER/ci-receipt.json` binds the tested source inputs. `tests/validate_distribution_receipt.py` only validates that captured receipt; it does not manufacture or re-run native evidence. Reviewers must read the actual GitHub jobs. Subsequent documentation/provenance commits require their own ordinary CI; matching release inputs explicitly indicate what can be reused.

No npm registry publication, main merge, independent review, branch-protection activation, model evaluation or production deployment is claimed. Existing Issues #2/#3 remain separate. Installation refuses conflicting user-owned native files rather than promising universal conflict-free migration.
