const fs = require("fs");
const path = require("path");
require("dotenv").config();

const PureChainImport = require("purechainlib");
const PureChain = PureChainImport.PureChain || PureChainImport;

const ROOT = path.resolve(__dirname, "..");
const CONTRACT_PATH = path.join(ROOT, "contracts", "CreditLedger.sol");
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

This document is updated by \`scripts/deploy_credit_ledger_purechainlib.js\`.

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

The deployment script also updates local \`.env\` keys:

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
  const privateKey = process.env.AEI_ETH_PRIVATE_KEY || process.env.PRIVATE_KEY || "";
  const rpcUrl = process.env.AEI_ETH_RPC_URL || process.env.RPC_URL || "https://purechainnode.com:8547";
  const expectedChainId = Number(process.env.PURECHAIN_CHAIN_ID || 900520900520);

  if (!privateKey) {
    throw new Error("AEI_ETH_PRIVATE_KEY or PRIVATE_KEY must be set in .env");
  }

  const purechain = new PureChain({
    name: "purechain",
    chainId: expectedChainId,
    rpcUrl,
    gasPrice: 0
  });
  purechain.connect(privateKey);

  const provider = purechain.getProvider();
  const signer = purechain.getSigner();
  if (!signer) {
    throw new Error("purechainlib did not create a signer");
  }

  const network = await provider.getNetwork();
  const chainId = Number(network.chainId);
  if (chainId !== expectedChainId) {
    throw new Error(`Unexpected chain ID: expected ${expectedChainId}, got ${chainId}`);
  }

  const deployerAddress = await signer.getAddress();
  const source = fs.readFileSync(CONTRACT_PATH, "utf8");
  const factory = await purechain.contract(source);
  const ledger = await factory.deploy();

  const contractAddress = await ledger.getAddress();
  const deploymentTx = ledger.deploymentTransaction ? ledger.deploymentTransaction() : ledger.deployTransaction;
  if (!deploymentTx || !deploymentTx.hash) {
    throw new Error("Missing CreditLedger deployment transaction");
  }

  const deploymentTxHash = deploymentTx.hash;
  const receipt = await provider.getTransactionReceipt(deploymentTxHash);
  if (!receipt) {
    throw new Error(`Missing deployment receipt for transaction ${deploymentTxHash}`);
  }

  const deploymentStatus = receipt.status === 1 ? "success" : "failed";
  if (deploymentStatus !== "success") {
    throw new Error(`CreditLedger deployment failed: tx=${deploymentTxHash} status=${receipt.status}`);
  }

  const code = await provider.getCode(contractAddress);
  if (!code || code === "0x") {
    throw new Error(`No contract bytecode found at ${contractAddress}`);
  }

  const block = await provider.getBlock(receipt.blockNumber);
  const deployedAt = block && block.timestamp
    ? new Date(Number(block.timestamp) * 1000).toISOString()
    : new Date().toISOString();

  const record = {
    network: "purechain",
    contract_address: contractAddress,
    chain_id: chainId,
    rpc_url: rpcUrl,
    deployer_address: deployerAddress,
    deployment_tx_hash: deploymentTxHash,
    deployment_status: deploymentStatus,
    block_number: Number(receipt.blockNumber),
    contract_name: "CreditLedger",
    deployed_at: deployedAt
  };

  writeDeploymentArtifacts(record);

  console.log("CreditLedger deployed with purechainlib");
  console.log(JSON.stringify(record, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
