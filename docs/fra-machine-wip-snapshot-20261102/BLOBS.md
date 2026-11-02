# Join overlay blob lock (looma-owned)

Source of truth: **looma-zervi** PR https://github.com/GenzLTD/looma-zervi/pull/39  
Vultr keeps an identical vendored copy of these 6 paths for FRA overseas runtime until deploy topology catches up.

| path | git blob |
| --- | --- |
| `backend/src/identity/__init__.py` | `b220c4ed060fc30af9beb7fb70fca4f2776d0b61` |
| `backend/src/identity/ledger_subject.py` | `0a0a0a9c28e8ef4065672bfc2d453c6795940c48` |
| `backend/src/payment/settlement.py` | `c45bde69b2e29ea8639d26a141205a7bab2f1e7f` |
| `backend/src/api/routes/payment_routes.py` | `d2a0ba59ef8cf1d6e02b960976600662bde93c81` |
| `backend/src/api/routes/huawei_iap_routes.py` | `393cf844a39da8224ba587eb75330f1e843bef1d` |
| `backend/src/db/manager.py` | `5359a60768794e9ec382fc7d3bf507bf84b20ac9` |

CI: `scripts/assert-looma-join-blobs.sh` must pass before merging staging secret workflow (#59) / FRA redeploy.