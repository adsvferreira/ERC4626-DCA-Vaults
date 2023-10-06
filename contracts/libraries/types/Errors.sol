// SPDX-License-Identifier: MIT

pragma solidity 0.8.21;

library Errors {
    error Forbidden(string message);
    error InvalidParameters(string message);
    /**
     * @dev Attempted to deposit more assets than the max amount for `receiver`.
     */
    error ERC4626ExceededMaxDeposit(
        address receiver,
        uint256 assets,
        uint256 max
    );
}
