// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AEI-V2G CreditLedger
/// @notice Redeemable credit-point ledger for V2G discharge incentives.
contract CreditLedger {
    struct Settlement {
        string evId;
        string stationId;
        uint256 kwhMilli;
        uint256 creditsAwarded;
        uint256 timestamp;
    }

    address public owner;
    uint256 public constant KWH_MILLI_PER_CREDIT = 500; // 0.5 kWh
    mapping(string => uint256) private balances;
    mapping(string => Settlement[]) private histories;

    event CreditsAwarded(
        string indexed evId,
        string stationId,
        uint256 kwhMilli,
        uint256 creditsAwarded,
        uint256 newBalance
    );
    event CreditsRedeemed(string indexed evId, uint256 amount, uint256 newBalance);

    modifier onlyOwner() {
        require(msg.sender == owner, "CreditLedger: owner only");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function award_credits(
        string calldata evId,
        string calldata stationId,
        uint256 kwhMilli
    ) external onlyOwner returns (uint256 creditsAwarded) {
        creditsAwarded = kwhMilli / KWH_MILLI_PER_CREDIT;
        balances[evId] += creditsAwarded;
        histories[evId].push(Settlement({
            evId: evId,
            stationId: stationId,
            kwhMilli: kwhMilli,
            creditsAwarded: creditsAwarded,
            timestamp: block.timestamp
        }));
        emit CreditsAwarded(evId, stationId, kwhMilli, creditsAwarded, balances[evId]);
    }

    function redeem_credits(string calldata evId, uint256 amount) external onlyOwner {
        require(balances[evId] >= amount, "CreditLedger: insufficient credits");
        balances[evId] -= amount;
        emit CreditsRedeemed(evId, amount, balances[evId]);
    }

    function get_balance(string calldata evId) external view returns (uint256) {
        return balances[evId];
    }

    function get_transaction_history(string calldata evId) external view returns (Settlement[] memory) {
        return histories[evId];
    }
}
