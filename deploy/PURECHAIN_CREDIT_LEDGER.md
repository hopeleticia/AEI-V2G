# Purechain CreditLedger Deployment

This document is updated by `scripts/deploy_credit_ledger_purechainlib.js`.

| Field | Value |
|---|---|
| Network | purechain |
| Contract name | CreditLedger |
| Contract address | `0x876a2e7d1EDC602A874B434a03dC66976c586bA3` |
| Chain ID | 900520900520 |
| RPC URL | https://purechainnode.com:8547 |
| Deployer address | `0x61b750EAB5D2e5fb36c91eEF196bE83561d4FE5d` |
| Deployment transaction | `0x23a202273b2d0e92ab22878f250c37ff9d179def72622bed3e2968a31333704c` |
| Deployment status | success |
| Block number | 1224556 |
| Deployed at UTC | 2026-05-22T01:59:59.000Z |

## Runtime Environment

After deployment, set:

```powershell
$env:AEI_ETH_RPC_URL="https://purechainnode.com:8547"
$env:AEI_ETH_PRIVATE_KEY="<your-private-key>"
$env:AEI_CREDIT_LEDGER_ADDRESS="0x876a2e7d1EDC602A874B434a03dC66976c586bA3"
```

The deployment script also updates local `.env` keys:

- `AEI_CREDIT_LEDGER_ADDRESS`
- `CREDIT_LEDGER_DEPLOY_TX`
