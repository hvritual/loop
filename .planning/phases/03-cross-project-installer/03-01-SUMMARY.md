# Cross-project installer — verified candidate

Intent: LOOP-INSTALLER. PR #4. Delivery target is the reviewable PR, not automatic main merge or registry publication.

Implemented install/update/doctor/uninstall/recover with an npm package entry, owned-file lifecycle, project-state preservation, staged official adapters and CLI tests. No custom workflow runtime was added.

Verification: 112 total tests (46 installer/regression); actual tarball smoke; eight actual CI compatibility jobs on093458821ec5ab2f04b1891fa8a5ac26779e3023, with exact input hashes in ci-receipt.json. GitHub source-export tree c06b12c250cdcb8bee20aabf118a373e695e2a4f was downloaded and reconstructed locally. Its code/contract hashes match the persisted execution records; gate verify and fresh-directory resume passed. Only source-bound evidence is reused, not a guessed main/branch state.

Artifacts: intent/spec/design/plan-map, ci-receipt.json, evidence-index.json, checkpoint.json, installation guide and installer validation guide. Local native execution is not claimed; GitHub jobs performed real native staging. Model login and semantic performance were not evaluated.

Independent review and integration decision remain pending. Existing Issues #2/#3 remain open. Next: read PR #4 current head/CI and perform authorized review/integration; do not restart already completed implementation.
