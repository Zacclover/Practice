# Offline translation notices

- Browser runtime: `@mkljczk/bergamot-translator` 0.4.16, vendored from the npm package without modification except for placement under this directory. License: **MPL-2.0**. Its full license text is in `LICENSE` and the original package README is retained in `README.md`.
- Translation model: Mozilla Firefox Translations `models/base/enzh`, English → Simplified Chinese (`zh-Hans`), metadata `byteSize: 42992955`, model hash `ce4486f728641a36269a245248dcb53405e76d96d9eba68dcb4172f29521e092`.
  - Upstream metadata: <https://github.com/mozilla/firefox-translations-models/blob/main/models/base/enzh/metadata.json>
  - Upstream licensing: <https://github.com/mozilla/firefox-translations-models/blob/main/LICENSE>
  - The model binaries are **not vendored**. The registry pins the matching content hashes and an immutable Hugging Face revision. The browser verifies SHA-256 before use and stores only verified responses in Cache Storage.

No submitted text is sent to the model host: it is only used to obtain the fixed model files; all translation runs in the vendored Web Worker/WASM runtime.
