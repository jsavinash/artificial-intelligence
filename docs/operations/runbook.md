# Operations Runbook

Day-2 procedures for on-call. Anything interacting with the serving path, MLflow,
or artifacts should be run from this runbook.

## 0. Always-on mental model

- **API boots even without a model**; `/ready` 503 until warm, `/health`
  reports `not-ready`. A 503 on `/ready` or `/predict` usually means the model
  artifact is missing, corrupt, or mismatched — **not** that the app crashed.
- The **artifacts mount is read-only** in production; the model is loaded into
  memory once per process at boot.
- **Model version** is the MLflow `run_id[:12]`, surfaced in `/health`,
  `/ready` and `/predict`.

---

## 1. Fast troubleshooting matrix

| Symptom | Likely cause | Action |
|---|---|---|
| `/ready` = 503 | Artifact missing / not mounted | §3 |
| `/predict` = 503 | Model not loaded | §3 |
| Boot `ArtifactIntegrityError` (sha256) | Tampered/corrupt artifact | §4 |
| Boot `ArtifactIntegrityError` (warmup) | Wrong feature count — train/serve skew | §5 |
| `[train] training_failed` | MLflow unreachable | §6 |
| `[train] exit 2` | Quality gate (`r2 < min_r2`) | §7 |
| High `5xx` | Mismatch between artifact contract & request | §3/§8 |
| Metrics missing | `/metrics` scrape target down (api unreachable) | Check pod/port 8000 |

---

## 2. Check current serving state

```bash
# Is the API warm?
curl -fsS http://<host>:8000/ready | jq .          # expect status "ok"
curl -fsS http://<host>:8000/health | jq .         # model_loaded true
curl -fsS http://<host>:8000/metrics | grep model_predictions_total

# What version is being served?
curl -fsS http://<host>:8000/ready | jq -r .model_version
```

---

## 3. Missing / not-mounted artifact (`/ready` 503)

1. Confirm `MODEL_ARTIFACT_PATH` matches the mount:
   ```bash
   # docker-compose reference: MODEL_ARTIFACT_PATH=/models/latest/pipeline.skops
   # and ../artifacts mounted read-only at /models
   ```
2. Check the artifact exists and `latest` symlink resolves:
   ```bash
   ls -l <repo>/artifacts/latest
   ls -l <repo>/artifacts/latest/pipeline.skops
   cat <repo>/artifacts/latest/manifest.json | jq .sha256
   ```
3. If `latest` is a broken symlink, re-run promotion:
   ```bash
   make export TRACKING_URI=<uri>
   ```
   or point `MODEL_ARTIFACT_PATH` at a specific `artifacts/<run-id>/pipeline.skops`.
4. Restart the API so `lifespan` re-loads.

---

## 4. SHA-256 mismatch at load

The artifact changed after export (or manifest is stale/wrong).

```bash
# Recomputed expected vs stored
cd <repo> && shasum -a 256 artifacts/latest/pipeline.skops
cat artifacts/latest/manifest.json | jq -r .sha256
```

**Action:** re-export from the MLflow run that actually produced this artifact;
do **not** hand-edit the manifest. Re-verify + restart.

---

## 5. Warmup/AIC shape error (train/serve skew)

`artifacts` trained on `N != 3` features will fail boot warmup.

1. Check `manifest.json` `params.feature_names`.
2. Confirm it matches `FEATURE_ORDER` in `schemas.py`.
3. Retrain with the correct contract (see §7) and re-export.

---

## 6. MLflow/training issues

- Server down **without** `--allow-fallback` → train exits `1`.
  Re-run with `--allow-fallback` to use sqlite (dev only), or restore server.
- **Production promotions must use the real tracking server** so lineage is
  intact.

---

## 7. Quality gate failure (`exit 2`)

Test `r2 < --min-r2` (default `0.40`). Treat as a **stop**: do not promote.

- Inspect metrics in MLflow UI for that run.
- If legitimate (data drift, bad alpha), fix training config and re-run, e.g.
  `make train ALPHA=0.5 MIN_R2=0.50`.
- If the gate is too strict/lenient, change `MIN_R2` deliberately + ADR.

---

## 8. Rolling back a model

Because artifacts are versioned under `artifacts/<run-id>/` and promoted via
the `latest` symlink, rollback = repoint the promotion:

```bash
# Keeps serving the current artifact; then:
ln -sfn <previous-run-id> <repo>/artifacts/latest
# restart API so lifespan reloads the previous version
```

Verify with `/ready` → `model_version == <previous-run-id[:12]>`, then run a
canary prediction. If pods mount per-deploy artifacts, redeploy old image/tag.

---

## 9. Restarting the local stack

```bash
make stack-logs     # tail logs
make stack-up       # rebuild + start (keeps volumes): API + MLflow + Prometheus
make stack-down     # stop (keep volumes)
make stack-nuke     # stop AND delete volumes (DESTROYS MLflow data)
```

---

## 10. Escalation

| Condition | Escalate to |
|---|---|
| Serving down beyond SLI, p99 latency breach, data corruption | Platform/SRE + Principal Architect |
| Repeated SHA-256 mismatches or artifact pipeline failures | Pipeline owner (ML engineer) |
| Anything touching security (secrets, unexpected access) | Security |

---
*Next: [Deployment](deployment.md)*