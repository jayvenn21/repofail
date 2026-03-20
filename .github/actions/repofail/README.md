# repofail GitHub Action

Run repofail on every PR: get a Markdown report as a comment and fail CI when compatibility violations exceed the threshold.

## Usage

In your repo, create `.github/workflows/repofail.yml`:

```yaml
name: repofail
on:
  pull_request:
    branches: [main, master]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jayvenn21/repofail/.github/actions/repofail@main
        with:
          path: .
          fail_on: HIGH
          comment: 'true'
          upload_artifact: 'true'
          pr_number: ${{ github.event.pull_request.number }}
```

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `path` | `.` | Repository path to scan |
| `fail_on` | `HIGH` | Fail CI when severity is HIGH, MEDIUM, or LOW |
| `comment` | `true` | Comment on PR with Markdown report |
| `upload_artifact` | `true` | Upload JSON report as workflow artifact |
| `pr_number` | (empty) | Set to `${{ github.event.pull_request.number }}` for PR comments |

## Behavior

1. Installs repofail from PyPI
2. Runs `repofail -m` and saves the report
3. Runs `repofail -j` for machine-readable output
4. Comments on the PR with the Markdown report (if `comment: true` and `pr_number` set)
5. Uploads `repofail.json` as an artifact (if `upload_artifact: true`)
6. Runs `repofail --ci` and fails the job if violations meet or exceed `fail_on`
