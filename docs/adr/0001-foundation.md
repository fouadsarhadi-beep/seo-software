# 0001 · Local application foundation

The first supported runtime is CPython 3.12. A Python package and console entry point are enough to use the existing analysis and test fixtures on Windows and Linux. The uv lockfile covers the development environment. Users can install a wheel or editable checkout with pip.

The maintained source is under `src/seo_analysis`. The ZIP in the repository records the original assessment input. Future changes belong in the source tree. Modules follow existing responsibilities, and the core tool catalogue lists implemented operations. The CLI dispatches to the application and analysis functions. A general runner will be validated against a complete networked audit and offline replay.

Per-user configuration selects storage locations. Each default crawl receives a distinct run directory. This gives the next stage a place to write durable observations before SQLite is introduced. The first audit will work without a project or connected account. Live providers will be added individually when their permission, credential and provenance contracts can be tested.

The interim sitemap command scopes reads to one explicit HTTP origin. Per-origin robots handling is needed before admitting additional origins. Stage B will enforce destination addresses at connection time, apply shared run budgets and persist partial results before the generic website audit is released.
