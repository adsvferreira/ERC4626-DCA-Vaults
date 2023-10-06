// SPDX-License-Identifier: MIT

pragma solidity 0.8.21;

library Events {
    // Automated Vault

    event CreatorFeeTransfered(
        address indexed vault,
        address indexed depositor,
        address indexed creator,
        uint256 shares
    );

    /**
     * @dev Attempted to deposit more assets than the max amount for `receiver`.
     */
    error ERC4626ExceededMaxDeposit(
        address receiver,
        uint256 assets,
        uint256 max
    );
}
