const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

const ROOT = path.resolve(__dirname, "..");
const DEPLOYMENT_PATH = path.join(ROOT, "deployments", "purechain_credit_ledger.json");
const DOC_PATH = path.join(ROOT, "deploy", "PURECHAIN_CREDIT_LEDGER.md");
const ENV_PATH = path.join(ROOT, ".env");

function updateEnvValue(contents, key, value) {
  const line = `${key}=${value}`;
  const pattern = new RegExp(`^${key}=.*$`, "m");
  if (pattern.test(contents)) {
    return contents.replace(pattern, line);
  }
  return `${contents.trimEnd()}\n${line}\n`;
}

function writeDeploymentArtifacts(record) {
  fs.mkdirSync(path.dirname(DEPLOYMENT_PATH), { recursive: true });
  fs.writeFileSync(DEPLOYMENT_PATH, `${JSON.stringify(record, null, 2)}\n`);

  const doc = `# Purechain CreditLedger Deployment

This document is updated by \`scripts/deploy_credit_ledger.js\`.

| Field | Value |
|---|---|
| Network | ${record.network} |
| Chain ID | ${record.chainId} |
| RPC URL | ${record.rpcUrl} |
| Contract | CreditLedger |
| Contract address | \`${record.contractAddress}\` |
| Deployment transaction | \`${record.deploymentTransactionHash}\` |
| Deployer | \`${record.deployer}\` |
| Deployed at UTC | ${record.deployedAtUtc} |

## Runtime Environment

After deployment, set:

\`\`\`powershell
$env:AEI_ETH_RPC_URL="${record.rpcUrl}"
$env:AEI_ETH_PRIVATE_KEY="<your-private-key>"
$env:AEI_CREDIT_LEDGER_ADDRESS="${record.contractAddress}"
\`\`\`

The deploy script also updates local \`.env\` keys:

- \`AEI_CREDIT_LEDGER_ADDRESS\`
- \`CREDIT_LEDGER_DEPLOY_TX\`
`;
  fs.writeFileSync(DOC_PATH, doc);

  if (fs.existsSync(ENV_PATH)) {
    let env = fs.readFileSync(ENV_PATH, "utf8");
    env = updateEnvValue(env, "AEI_CREDIT_LEDGER_ADDRESS", record.contractAddress);
    env = updateEnvValue(env, "CREDIT_LEDGER_DEPLOY_TX", record.deploymentTransactionHash);
    fs.writeFileSync(ENV_PATH, env);
  }
}

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  const network = hre.network.name;
  const chainId = Number((await hre.ethers.provider.getNetwork()).chainId);
  const rpcUrl = process.env.RPC_URL || process.env.AEI_ETH_RPC_URL || "";

  const CreditLedger = await hre.ethers.getContractFactory("CreditLedger");
  const ledger = await CreditLedger.deploy();

  if (ledger.waitForDeployment) {
    await ledger.waitForDeployment();
  } else if (ledger.deployed) {
    await ledger.deployed();
  }

  const contractAddress = ledger.target || ledger.address;
  const deploymentTx = ledger.deploymentTransaction ? ledger.deploymentTransaction() : ledger.deployTransaction;
  const deploymentTransactionHash = deploymentTx.hash;

  const record = {
    network,
    chainId,
    rpcUrl,
    contractName: "CreditLedger",
    contractAddress,
    deploymentTransactionHash,
    deployer: deployer.address,
    deployedAtUtc: new Date().toISOString()
  };

  writeDeploymentArtifacts(record);

  console.log("CreditLedger deployed");
  console.log(JSON.stringify(record, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
