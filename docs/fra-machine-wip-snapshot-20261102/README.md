# FRA machine WIP snapshot (2026-11-02)

Retrieved from `45.76.84.90:/opt/looma-zervi/backend` (container `looma-backend` bind-mount).

## What this branch is
- Base: Vultr-Genzltd `origin/main` (already has membership + settlement).
- Overlay: FRA **hand join** patches (`identity/ledger_subject.py` + settlement/payment/huawei/manager wiring).
- **Not** looma-zervi #38 as-shipped. #38 has no `settlement.py`; FRA upgrade→status walks machine settlement path.

## bak-join validity
Directory `.bak-join-20261102-120551` (copied under `bak/`):
- payment_routes / huawei_iap_routes / manager: sha256 **identical** to then-current → **not** pre-join originals.
- settlement: bak ≠ current (both already contain ledger imports; neither equals Vultr main clean settlement).
- **Invalid rollback** to pre-join tree. Pre-join settlement = Vultr git `backend/src/payment/settlement.py` @ main.

## git_commit.txt
Machine file content `e18b794…` written `2026-10-28 15:36Z` — same timestamp as container create. Writers: Vultr `deploy.yml` / staging rsync (`echo $SHA > backend/git_commit.txt`). Health reads that marker, so `/health.git_commit` reports **Vultr deploy SHA**, not looma #38 tip.