require("dotenv").config();
require("@nomicfoundation/hardhat-ethers");

const privateKey = process.env.PRIVATE_KEY || process.env.AEI_ETH_PRIVATE_KEY || "";
const rpcUrl = process.env.RPC_URL || process.env.AEI_ETH_RPC_URL || "https://purechainnode.com:8547";
const chainId = Number(process.env.PURECHAIN_CHAIN_ID || 900520900520);

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    purechain: {
      url: rpcUrl,
      chainId,
      accounts: privateKey ? [privateKey] : []
    }
  }
};
