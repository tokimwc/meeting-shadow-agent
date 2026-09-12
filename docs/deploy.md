# Deploying to Cloud Run

One service, one region, one image repository:

- project `meeting-shadow-toki-260907` (number 610585392846), region `asia-northeast1`
- service `meeting-shadow`, runtime SA `msa-runtime@…`, min 0 / max 1, concurrency 4
- image `asia-northeast1-docker.pkg.dev/meeting-shadow-toki-260907/msa/app:<version>`
- behind IAP: anonymous requests get a 302 to `accounts.google.com`, including `/health`

## Release

Build, then swap only the image. Everything else (env vars, the Secret Manager
reference, the service account, scaling) is carried over from the previous
revision, which is also why this avoids the `--set-env-vars` trap below.

```bash
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/meeting-shadow-toki-260907/msa/app:0.1.13 \
  --project meeting-shadow-toki-260907 --region asia-northeast1 .

gcloud run deploy meeting-shadow --image asia-northeast1-docker.pkg.dev/meeting-shadow-toki-260907/msa/app:0.1.13 \
  --region asia-northeast1 --project meeting-shadow-toki-260907
```

Check the upload set before submitting, so an ignore rule cannot silently drop
the demo audio:

```bash
gcloud meta list-files-for-upload
```

`app/static/samples/sample-01.wav` must be in the list; `samples/` (root),
`.venv/`, `.worktrees/` and `.claude/` must not. Read the whole list, not just those names:
`.claude/settings.local.json` reached the 0.1.13 context because it is gitignored rather than
`.gcloudignore`d, and the two files are unrelated.

Verify, in this order:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://meeting-shadow-610585392846.asia-northeast1.run.app/   # 302
gcloud run revisions describe <new-revision> --region asia-northeast1 \
  --project meeting-shadow-toki-260907 --format="value(spec.containers[0].env)"                          # env + secret intact
```

then sign in through IAP in a browser and run the sample path end to end.

## Rollback

Traffic is pinned to the latest revision, so rolling back means naming the old one:

```bash
gcloud run services update-traffic meeting-shadow --region asia-northeast1 \
  --project meeting-shadow-toki-260907 --to-revisions=meeting-shadow-00008-698=100
```

`gcloud run revisions list --region asia-northeast1 --project meeting-shadow-toki-260907`
lists what is available.

## Traps already paid for

Each of these cost a debugging session once. Details are in the vault
`.claude/ERRORS.md`.

- **Secret Manager values pick up CRLF** when written through a PowerShell pipe,
  and a trailing `\r\n` makes an `Authorization` header illegal. Write the value
  as bytes (`cmd /c "python emit.py | … --data-file=-"`), and `settings.py`
  strips on read as a second line of defence.
- **`.gcloudignore` patterns match at every level.** `samples/` also excluded
  `app/static/samples/`, so the demo WAV was missing from the container. Anchor
  it: `/samples/`.
- **setuptools `package-data` is not recursive.** `static/*` does not cover
  `static/samples/*`; both entries are needed or the WAV never reaches the wheel.
- **PowerShell joins comma-separated `--set-env-vars` into one value**, which
  made Vertex return `CONSUMER_INVALID` 403. Use the alternate separator form
  `"^;^KEY1=v1;KEY2=v2"` — or, as above, do not pass env vars on a normal release.
- **gcloud 520 has no `--iap` flag.** IAP was enabled through the Cloud Run v2
  REST API (`iapEnabled: true`); binding the OAuth client succeeded only via
  `gcloud iap settings set` at project level with a temporary YAML file, not via
  `updateIapSettings`.
- **The IAP resource name uses an underscore**:
  `projects/610585392846/iap_web/cloud_run-asia-northeast1/services/meeting-shadow`.
  `cloud-run` does not resolve.
- **Do not name a health endpoint `/healthz`.** Cloud Run reserves some paths
  ending in `z`; they return a Google Front End 404 before reaching the
  container. This service uses `/health`.

## Releases

| Version | Revision | What changed |
|---|---|---|
| 0.1.7 | `meeting-shadow-00008-698` | prompt separation, 450 ms turn batching, eval hardening, a11y |
| 0.1.13 | `meeting-shadow-00014-26t` | the authority contract and the verdict on the card |
| 0.1.14 | `meeting-shadow-00015-v4c` | structured events, so adoption can be measured |

Rolling back 0.1.14 means naming `meeting-shadow-00014-26t`.

## Reading the events

There is no database: `emit()` in [`app/main.py`](../app/main.py) writes one JSON line to stdout and
Cloud Run parses it into `jsonPayload`. Nothing to provision, nothing to migrate.

```bash
gcloud logging read 'jsonPayload.msa_event="card"' --limit 200 --format=json   --project meeting-shadow-toki-260907
```

`msa_event` is `card` for what the engineer did with one, `suggested` for a generated suggestion and
`refused` for one this code would not show. If the volume ever justifies it, a log sink into BigQuery
is a console setting and needs no code.
