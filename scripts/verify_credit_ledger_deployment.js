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

This document is updated by \`scripts/verify_credit_ledger_deployment.js\` after a manual Remix/MetaMask deployment, or by \`scripts/deploy_credit_ledger.js\` after a Hardhat deployment.

| Field | Value |
|---|---|
| Network | ${record.network} |
| Contract name | ${record.contract_name} |
| Contract address | \`${record.contract_address}\` |
| Chain ID | ${record.chain_id} |
| RPC URL | ${record.rpc_url} |
| Deployer address | \`${record.deployer_address}\` |
| Deployment transaction | \`${record.deployment_tx_hash}\` |
| Deployment status | ${record.deployment_status} |
| Block number | ${record.block_number} |
| Deployed at UTC | ${record.deployed_at} |

## Runtime Environment

After deployment, set:

\`\`\`powershell
$env:AEI_ETH_RPC_URL="${record.rpc_url}"
$env:AEI_ETH_PRIVATE_KEY="<your-private-key>"
$env:AEI_CREDIT_LEDGER_ADDRESS="${record.contract_address}"
\`\`\`

The verification script also updates local \`.env\` keys:

- \`AEI_CREDIT_LEDGER_ADDRESS\`
- \`CREDIT_LEDGER_DEPLOY_TX\`
`;
  fs.writeFileSync(DOC_PATH, doc);

  if (fs.existsSync(ENV_PATH)) {
    let env = fs.readFileSync(ENV_PATH, "utf8");
    env = updateEnvValue(env, "AEI_CREDIT_LEDGER_ADDRESS", record.contract_address);
    env = updateEnvValue(env, "CREDIT_LEDGER_DEPLOY_TX", record.deployment_tx_hash);
    fs.writeFileSync(ENV_PATH, env);
  }
}

async function main() {
  const network = hre.network.name;
  const chainId = Number((await hre.ethers.provider.getNetwork()).chainId);
  const rpcUrl = process.env.RPC_URL || process.env.AEI_ETH_RPC_URL || "";
  const txHash = process.env.CREDIT_LEDGER_DEPLOY_TX || process.env.DEPLOYMENT_TX_HASH || "";
  const configuredAddress = process.env.AEI_CREDIT_LEDGER_ADDRESS || "";

  if (!txHash) {
    throw new Error("Set CREDIT_LEDGER_DEPLOY_TX or DEPLOYMENT_TX_HASH to the Remix/MetaMask deployment transaction hash");
  }

  const receipt = await hre.ethers.provider.getTransactionReceipt(txHash);
  if (!receipt) {
    throw new Error(`Missing deployment receipt for transaction ${txHash}`);
  }

  const deploymentStatus = receipt.status === 1 ? "success" : "failed";
  if (deploymentStatus !== "success") {
    throw new Error(`CreditLedger deployment failed: tx=${txHash} status=${receipt.status}`);
  }

  const contractAddress = configuredAddress || receipt.contractAddress || "";
  if (!contractAddress) {
    throw new Error("Could not determine contract address; set AEI_CREDIT_LEDGER_ADDRESS in .env");
  }
  if (configuredAddress && receipt.contractAddress && configuredAddress.toLowerCase() !== receipt.contractAddress.toLowerCase()) {
    throw new Error(
      `Configured AEI_CREDIT_LEDGER_ADDRESS (${configuredAddress}) does not match receipt contractAddress (${receipt.contractAddress})`
    );
  }

  const code = await hre.ethers.provider.getCode(contractAddress);
  if (!code || code === "0x") {
    throw new Error(`No contract bytecode found at ${contractAddress}`);
  }

  const tx = await hre.ethers.provider.getTransaction(txHash);
  if (!tx) {
    throw new Error(`Missing deployment transaction details for ${txHash}`);
  }

  const block = await hre.ethers.provider.getBlock(receipt.blockNumber);
  const deployedAt = block && block.timestamp
    ? new Date(Number(block.timestamp) * 1000).toISOString()
    : new Date().toISOString();

  const record = {
    network,
    contract_address: contractAddress,
    chain_id: chainId,
    rpc_url: rpcUrl,
    deployer_address: tx.from,
    deployment_tx_hash: txHash,
    deployment_status: deploymentStatus,
    block_number: Number(receipt.blockNumber),
    contract_name: "CreditLedger",
    deployed_at: deployedAt
  };

  writeDeploymentArtifacts(record);

  console.log("CreditLedger deployment verified");
  console.log(JSON.stringify(record, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
