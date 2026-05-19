# Purechain CreditLedger Deployment

This document is updated by `scripts/deploy_credit_ledger.js`.

| Field | Value |
|---|---|
| Network | purechain |
| Chain ID | 900520900520 |
| RPC URL | https://purechainnode.com:8547 |
| Contract | CreditLedger |
| Contract address | `PENDING` |
| Deployment transaction | `PENDING` |
| Deployer | `PENDING` |
| Deployed at UTC | PENDING |

## Deploy

1. Put your private key in `.env`:

```text
PRIVATE_KEY=<your-private-key>
AEI_ETH_PRIVATE_KEY=<your-private-key>
```

2. Install contract tooling:

```powershell
npm install
```

3. Deploy:

```powershell
npm run deploy:credit-ledger:purechain
```

The deploy script updates:

- `deploy/PURECHAIN_CREDIT_LEDGER.md`
- `deployments/purechain_credit_ledger.json`
- `.env` keys `AEI_CREDIT_LEDGER_ADDRESS` and `CREDIT_LEDGER_DEPLOY_TX`
