# SOW-0012 - Fix deploy.yml build: Go toolchain too old and branding check greps wrong output

## Status

Status: completed

Sub-state: delivered; fix validated by full local build replicating the workflow steps.

## Requirements

### Purpose

Make the `PulseNode Deployment & Verification` GitHub Actions workflow (`.github/workflows/deploy.yml`) build and verify the agent successfully. Every run of this workflow has failed, including the run for the latest `main` commit that attempted to fix build dependencies.

### User Request

"fix the build"

### Assistant Understanding

Facts:

- `.github/workflows/deploy.yml` job `Compile & Verify Agent` fails at the CMake configure step on every run.
- Latest failing run for `main` HEAD: run 25562874102 (job 75038759634). Error: `Could NOT find Go: Found unsuitable version "1.24.13", but required is at least "1.25.7" (found /usr/bin/go)` raised from `packaging/cmake/Modules/FindGo.cmake:62` via `CMakeLists.txt:388`.
- `src/go/go.mod:3` declares `go 1.25.7`. `find_min_go_version()` (`packaging/cmake/Modules/NetdataGoTools.cmake:61-77`) scans all `go.mod` files and takes the highest `go` directive, so the build requires Go >= 1.25.7.
- The workflow never installs Go; it relies on the runner image default, which is older than 1.25.7.
- The workflow builds with raw `cmake` + `ninja` (a deliberate direction set by commit 74a8547 "Fix deployment: Switch to CMake for building PulseNode"), which means it bypasses the project's supported source-build entry point `netdata-installer.sh`. That installer computes feature flags from what is actually installed (`packaging/installer/functions.sh:275-395` `prepare_cmake_options`, `check_for_feature`), while raw CMake enables most optional features unconditionally (`DEFAULT_FEATURE_STATE=True`, `CMakeLists.txt:128`) and hard-fails configure when their libraries are absent.
- With `DEFAULT_FEATURE_STATE=True`, the hard-failing optional features on a runner without their dev libraries are: FreeIPMI (`CMakeLists.txt:2725` `pkg_check_modules(IPMI REQUIRED libipmimonitoring)`), NFACCT (`CMakeLists.txt:2751`), XenStat (`CMakeLists.txt:2773`), and the Prometheus remote-write exporter (`CMakeLists.txt:3136-3148`, `FATAL_ERROR` when snappy is absent). CUPS (`CMakeLists.txt:2832-2852`) and the MongoDB exporter (`CMakeLists.txt:3126-3129`) degrade gracefully. eBPF builds but pulls external libbpf/co-re artifacts; `netdata-installer.sh` defaults it off (`functions.sh`: `enable_feature PLUGIN_EBPF "${ENABLE_EBPF:-0}"`).
- Protobuf is unconditionally required by the default configure (`CMakeLists.txt:823` -> `netdata_detect_protobuf`, `packaging/cmake/Modules/NetdataProtobuf.cmake:128` `find_package(Protobuf REQUIRED)` when not bundled). Neither the workflow's original apt list nor `install-required-packages.sh netdata-all` installs protobuf on Ubuntu (the installer path bundles protobuf instead: `functions.sh` `enable_feature BUNDLED_PROTOBUF 1` by default). Discovered by local replication: with Go fixed, configure fails next with `Could NOT find Protobuf`. json-c and libyaml do not hard-fail the same way — `NetdataJSONC.cmake:72-76` and `NetdataYAML.cmake` fall back to bundled copies when the system library is absent.
- FLEX/BISON are required by the vendored libsensors build (`src/collectors/debugfs.plugin/libsensors/CMakeLists.txt:15` `find_package(FLEX REQUIRED)`); missing from the workflow's original apt list but provided by `install-required-packages.sh` (`pkg_bison`/`pkg_flex` maps). Discovered by local replication after protobuf was satisfied.
- The repo's own CI installs source-build dependencies via `packaging/installer/install-required-packages.sh --dont-wait --non-interactive netdata-all` (`.github/workflows/build.yml:1175`), which is the maintained package map (covers json-c, yaml, systemd, flex, bison, and the core libs) and is the right thing for this workflow to reuse instead of a hand-rolled apt list.
- The fork's git tree contains NO gitlink (mode 160000) entries for the three submodules declared in `.gitmodules` — they were dropped when the fork was created (`git ls-tree HEAD` shows no gitlinks at the declared paths; `git submodule status` is empty). Without them, CMake's generate step fails on the vendored libsensors sources (`Cannot find source file: vendored/lib/access.c`, `src/collectors/debugfs.plugin/libsensors/CMakeLists.txt:5`), and the ACLK protobuf sources referenced at `CMakeLists.txt:2212-2221` would fail the compile. No `submodules:` setting on checkout can fix this — there is nothing in the tree for checkout to initialize. The build needs `src/aclk/aclk-schemas` and `src/collectors/debugfs.plugin/libsensors/vendored`; `src/web/server/h2o/libh2o` is referenced nowhere in the build system (stale `.gitmodules` entry, also gitlink-less in upstream netdata master).
- Correct pins: `src/collectors/debugfs.plugin/libsensors/vendored` -> `42f240d2a457834bcbdf4dc8b57237f97b5f5854` (upstream `netdata/netdata @ master` gitlink via blobless partial clone; matches this fork's own `src/collectors/debugfs.plugin/libsensors/libsensors.version` exactly, cross-confirming it). `src/aclk/aclk-schemas` -> `844c984b57caaf573f7d3941d64b2fc83537a22f`: upstream master's current pin (`db1f9d85`) proved too new for this fork — `netdata/aclk-schemas` commit `deeeb4b` ("Upgrade to Buf v2", #57) changed proto imports from `proto/aclk/v1/lib.proto` style to `aclk/v1/lib.proto` style, and this fork's protoc invocation passes `-I<aclk-schemas root>` which only resolves the old style. Build with `db1f9d85` failed at protoc (`aclk/v1/lib.proto: File not found`); `844c984` is the last commit with the old-style imports and matches this fork's CMake era.
- The final step `Verify Startup Sequence` runs `./build/src/daemon/netdata -W buildinfo | grep "PulseNode"`. Two defects: (a) `-W buildinfo` calls `print_build_info()` (`src/daemon/main.c:821-824`), whose output (`src/daemon/buildinfo.c`) contains no "PulseNode" string — the PulseNode banner exists only in the help output (`src/daemon/main.c:104-117`), printed to stdout by `help(0)` on `-h` (`src/daemon/main.c:321-322`); and (b) the binary path is wrong — CMake places the `netdata` executable at `${CMAKE_BINARY_DIR}/netdata` (`build/netdata`), not `build/src/daemon/netdata` (verified on the local build: only `build/netdata` exists).

Inferences:

- Even after fixing the Go toolchain, the verify step would fail because `grep "PulseNode"` on buildinfo output matches nothing (grep exits 1).
- `actions/checkout@v4` emits Node.js 20 deprecation warnings (forced to Node 24 since 2026-06-02); the rest of the repo already uses `actions/checkout@v6`.

Unknowns:

- None blocking. Workflow triggers on push/PR to `main`, so the fix can only be exercised in CI after it lands on `main`; local replication is the pre-merge validation.

### Acceptance Criteria

- CMake configure succeeds with the dependency set installed by the workflow plus a Go >= 1.25.7 toolchain. Verified by local replication.
- Full `ninja` build completes and `./build/src/daemon/netdata -W buildinfo` runs successfully. Verified by local replication.
- The branding check matches: `./build/src/daemon/netdata -h | grep "PulseNode"` finds the banner. Verified by local replication.

## Analysis

Sources checked:

- CI logs of run 25562874102 (deploy.yml, `main` @ 94c094e) via GitHub API.
- `.github/workflows/deploy.yml`, `.github/workflows/packaging.yml:211-215`, `.github/workflows/build.yml:367-369`.
- `packaging/cmake/Modules/FindGo.cmake`, `packaging/cmake/Modules/NetdataGoTools.cmake:54-77`.
- `CMakeLists.txt` required dependencies (`REQUIRED` scan: pkg-config, libcurl, libcrypto, zlib, liblz4, uuid, libuv, Go).
- `src/go/go.mod`, `src/web/mcp/bridges/stdio-golang/go.mod` (go 1.25.7 and 1.24.0; max is 1.25.7).
- `src/daemon/main.c` (help banner, `-W buildinfo` dispatch), `src/daemon/buildinfo.c` (no PulseNode string).

Current state:

- Every run of `deploy.yml` has failed. The two most recent `main` commits ("Fix deployment: Switch to CMake for building PulseNode", "Fix: Add missing build dependencies for Ubuntu runner") fixed earlier failures (build system choice, missing dev packages) but the Go version and branding-grep defects remained.

Risks:

- Low. Changes are confined to one workflow file; no product code, packaging, or docs behavior changes.

## Pre-Implementation Gate

Status: ready

Problem / root-cause model:

- Two independent defects in `.github/workflows/deploy.yml`:
  1. The build requires Go >= 1.25.7 (highest `go` directive across `go.mod` files, enforced by `find_package(Go ${MIN_GO_VERSION} REQUIRED)` at `CMakeLists.txt:388`), but the workflow never sets up Go and the runner default is older. Configure fails; reproduced locally with Go 1.24.7 producing the identical error.
  2. The verify step greps `-W buildinfo` output for "PulseNode", but that string exists only in the `-h` help banner, so the step would fail even with a successful build.

Evidence reviewed:

- Failing CI log for run 25562874102 (exact CMake error and step transcript).
- Local reproduction: `cmake .. -G Ninja` with Go 1.24.7 fails with `Could NOT find Go: Found unsuitable version "1.24.7", but required is at least "1.25.7"`.
- Code paths cited under Assistant Understanding.

Affected contracts and surfaces:

- `.github/workflows/deploy.yml` only (CI surface). No runtime, packaging, or docs contracts change.

Existing patterns to reuse:

- `actions/setup-go@v6` with `go-version-file: src/go/go.mod` exactly as used in `.github/workflows/packaging.yml:211-215` (keeps the CI Go version in lockstep with the `go.mod` that drives CMake's minimum).
- `actions/checkout@v6` as used by the repo's other workflows.

Risk and blast radius:

- Limited to one CI workflow. Worst case the workflow still fails, which is the current steady state. No user-facing behavior changes.

Sensitive data handling plan:

- No secrets, tokens, customer data, or private endpoints are involved. CI log excerpts quoted in this SOW contain only public build output. Nothing to redact.

Implementation plan:

1. Restore the missing submodule gitlinks: `src/aclk/aclk-schemas @ 844c984` (last pre-Buf-v2 commit, matching this fork's protoc include layout) and `src/collectors/debugfs.plugin/libsensors/vendored @ 42f240d2` (upstream netdata's pin, cross-confirmed by `libsensors.version`).
2. In `deploy.yml`: check out with `submodules: recursive`; add a `Set up Go` step (`actions/setup-go@v6`, `go-version-file: src/go/go.mod`); bump `actions/checkout@v4` to `@v6`.
3. In `deploy.yml`: replace the hand-rolled apt list with `packaging/installer/install-required-packages.sh --dont-wait --non-interactive netdata-all` plus explicit `ninja-build libprotobuf-dev protobuf-compiler` (ninja and system protobuf are not covered by the script).
4. In `deploy.yml`: pass `-DENABLE_PLUGIN_FREEIPMI=Off -DENABLE_PLUGIN_NFACCT=Off -DENABLE_PLUGIN_XENSTAT=Off -DENABLE_PLUGIN_EBPF=Off -DENABLE_EXPORTER_PROMETHEUS_REMOTE_WRITE=Off` to configure — the same result `netdata-installer.sh` would compute for this dependency set (features whose libraries the maintained package map does not provide; eBPF also defaults off in the installer).
5. Change the verify step to run `./build/netdata -W buildinfo` (startup/buildinfo check) and grep `./build/netdata -h` for "PulseNode" (branding check), using the actual binary location.

Validation plan:

- Replicate the full workflow locally: run `install-required-packages.sh netdata-all` plus the explicit apt packages, provide Go 1.25.7 (`GOTOOLCHAIN=go1.25.7`; CI gets it via setup-go), run the exact configure command from the workflow, `ninja`, then both verify commands. Local-only deviation: `-DDASHBOARD_URL=file://...` pointing at a stub tarball, because this sandbox's egress policy blocks `app.netdata.cloud` (CONNECT 403) while GitHub runners have open egress; the dashboard is fetch-and-install of static files and does not affect the compiled binary.

Artifact impact plan:

- AGENTS.md: unaffected; no workflow/process rule changes.
- Runtime project skills: unaffected; no skill covers this repo's CI build workflow.
- Specs: unaffected; no product behavior or contract changes.
- End-user/operator docs: unaffected; internal CI only.
- End-user/operator skills: unaffected.
- SOW lifecycle: single new SOW; completed and moved to done/ in the same commit as the fix.

Open-source reference evidence:

- No mirrored repositories under `/opt/baddisk/monitoring/repos/` were consulted; the failure is fully explained by this repository's own workflow, CMake modules, and CI logs.

Open decisions:

- None. The fix reuses the repo's own established setup-go pattern; no product/design fork.

## Implications And Decisions

None required from the user; no design forks. The verify-step intent ("PulseNode Core Branding Verified") is preserved by grepping the output that actually carries the branding.

## Plan

1. Edit `.github/workflows/deploy.yml` (setup-go, checkout bump, verify-step fix). Low risk.
2. Validate via full local build replication.
3. Complete SOW and commit workflow fix + SOW together.

## Execution Log

### 2026-07-13

- Reproduced the configure failure locally with Go 1.24.7 (identical error to CI run 25562874102).
- Iterated local replication, discovering each downstream failure in turn: missing protobuf (hard-required), missing flex/bison (vendored libsensors), all-default optional plugins hard-requiring libipmimonitoring/libnetfilter_acct/xenstat/snappy, and finally the missing submodule gitlinks (generate-step failure on `vendored/lib/access.c`).
- Restored submodule gitlinks `src/aclk/aclk-schemas @ 844c984` (first tried upstream master's pin `db1f9d85`; protoc failed on the Buf-v2 import style, re-pinned to the last pre-Buf-v2 commit) and `src/collectors/debugfs.plugin/libsensors/vendored @ 42f240d2`.
- Edited `.github/workflows/deploy.yml`: checkout v4 -> v6 with `submodules: recursive`; added `Set up Go` (`actions/setup-go@v6`, `go-version-file: src/go/go.mod`); dependency install now uses `install-required-packages.sh netdata-all` + `ninja-build libprotobuf-dev protobuf-compiler`; configure disables FREEIPMI/NFACCT/XENSTAT/EBPF/PROMETHEUS_REMOTE_WRITE; verify step runs `-W buildinfo` unfiltered and greps `-h` output for "PulseNode".
- Ran full local replication of the final workflow steps (dependency script, configure with the exact workflow flags, `ninja`, both verify commands) with Go 1.25.7. The first verify attempt exposed the wrong binary path (`build/src/daemon/netdata` does not exist; the executable is `build/netdata`); fixed the workflow path and re-ran both verify commands successfully.

## Validation

Acceptance criteria evidence:

- Configure: succeeds with Go 1.25.7, the `netdata-all` package set plus ninja/protobuf, restored submodules, and the workflow's exact `-D` flags ("Configuring done", "Generating done").
- Build: `ninja` completed with exit status 0 (806 targets initially, 460 after the aclk-schemas re-pin resume), producing `build/netdata` (~97 MB) plus plugins (go.d.plugin, otel-plugin, apps.plugin, etc.).
- Verify: `./build/netdata -W buildinfo` printed the full build info (`Netdata Version: v2.10.0-161-nightly`) and exited 0; `./build/netdata -h | grep "PulseNode"` matched the banner lines and exited 0.

Tests or equivalent validation:

- Full local replication of every workflow step on Linux (Ubuntu 24.04 userland, same as `ubuntu-latest`) with Go 1.25.7 (the version `actions/setup-go` resolves from `src/go/go.mod`; provided locally via `GOTOOLCHAIN=go1.25.7`). Negative controls: configure with Go 1.24.7 reproduced the CI Go failure verbatim; configure without protobuf, without flex, with default plugin flags, and with missing/mispinned submodules each reproduced the corresponding downstream failure before its fix.
- Local-only deviation from CI, with rationale: `-DDASHBOARD_URL=file://<stub>.tar.gz` because this sandbox blocks `app.netdata.cloud` (CONNECT 403) while GitHub runners have open egress; the dashboard step only fetches and installs static files and does not affect compilation or the verify step.

Real-use evidence:

- The built `netdata` binary was executed (`-W buildinfo`, `-h`) — the same invocations the workflow's verify step performs, from the same relative path the workflow uses.

Reviewer findings:

- Self-review of the diff: `deploy.yml` changes are confined to the five planned fixes; the only tree changes are the two restored gitlinks (no `.gitmodules` change — the original file already declared both paths; the duplicate section `git submodule add` appended was reverted). No second reviewer available in this session.

Same-failure scan:

- Searched all workflows for other jobs invoking CMake without Go setup: `packaging.yml` and `build.yml` already use `actions/setup-go@v6`; `checks.yml` builds via `netdata-installer.sh` inside containers with their own toolchains. No other workflow greps buildinfo for "PulseNode" or uses the wrong binary path.
- The missing-gitlink defect affects every consumer of this repository (any fresh clone), not just this workflow; restoring the gitlinks fixes them all.

Sensitive data gate:

- SOW and workflow diff contain no secrets, tokens, customer identifiers, or private endpoints.

Artifact maintenance gate:

- AGENTS.md: no update needed; no workflow-of-work or guardrail changes (evidence: change is a CI bugfix inside `.github/workflows/`).
- Runtime project skills: no update needed; no `.agents/skills/project-*` skill covers GitHub Actions CI for this repo, and no new recurring how-to knowledge beyond this SOW.
- Specs: no update needed; no product behavior, contract, schema, or packaging output changed.
- End-user/operator docs: none affected; `deploy.yml` is not documented in README or docs (verified by grep for `deploy.yml` in docs/README).
- End-user/operator skills: none affected; no docs/spec changes occurred.
- SOW lifecycle: `Status: completed` in `.agents/sow/done/`, committed together with the workflow fix in one commit.

Specs update:

- Not needed: the change affects only CI workflow mechanics, not what the project does.

Project skills update:

- Not needed: no runtime skill's trigger covers CI build workflows; the durable knowledge (root cause, evidence, fix pattern) is recorded in this SOW.

End-user/operator docs update:

- Not needed: no human-facing documentation references this workflow or its behavior.

End-user/operator skills update:

- Not needed: no docs/spec changes were made.

Lessons:

- `find_min_go_version()` means any `go.mod` bump silently raises the CI Go requirement; workflows must derive Go from `go-version-file: src/go/go.mod` rather than pinning or relying on runner defaults.
- Branding strings live in the help output, not in buildinfo; verification greps must target the output that actually carries the string being asserted, and verify commands must use the real artifact path (`build/netdata`, not `build/src/daemon/netdata`).
- Raw `cmake` builds of this tree enable most optional features (`DEFAULT_FEATURE_STATE=True`) and hard-fail on their missing libraries; either install the full dependency set or explicitly disable the features `netdata-installer.sh` would have auto-disabled.
- This fork's tree lost its submodule gitlinks at fork time; any future "file not found" in vendored paths should be checked against `.gitmodules` vs `git ls-tree` first.
- Submodule pins must match the CMake era of the superproject: aclk-schemas commits after "Upgrade to Buf v2" (#57) changed proto import style and require newer protoc include flags than this fork's CMake passes.

Follow-up mapping:

- Release/CodeQL workflow failures: rejected as out of scope for this SOW; surfaced to the user as a pending product/ops decision (see Followup).
- On-runner CI confirmation: tracked in Followup; requires the change to reach `main`, which is a user-controlled merge action.
- All other discovered defects: implemented in this SOW.

## Outcome

Delivered. `.github/workflows/deploy.yml` fixed (Go toolchain setup, submodule checkout, maintained dependency script, explicit feature flags, corrected verify step) and the two build-critical submodule gitlinks restored (`src/aclk/aclk-schemas @ 844c984`, `src/collectors/debugfs.plugin/libsensors/vendored @ 42f240d2`). Full workflow pipeline (configure, build, verify) replicated locally and green; the built agent prints its build info and the PulseNode banner.

## Lessons Extracted

See Validation > Lessons.

## Followup

- The nightly `Release` workflow and `CodeQL` workflow also fail on `main` for unrelated reasons (missing repository secrets/token configuration inherited from upstream Netdata automation, e.g. checkout fails with "Input required and not supplied: token"). Out of scope for this SOW ("fix the build" = the deployment build workflow); flagged to the user for a decision on whether to configure secrets or disable those inherited workflows. Tracked as a user decision, not as a pending SOW, because the remedy (secrets vs. disabling) is a product/ops choice.
- CI confirmation on a real runner requires this change to reach `main` (the workflow triggers on push/PR to `main`); the branch push alone does not trigger it.

## Regression Log

None yet.
