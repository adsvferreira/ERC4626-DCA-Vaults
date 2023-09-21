// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";

interface IAutomatedVault {
    function setLastUpdatePerDepositor(address depositor) external;

    function getInitMultiAssetVaultParams()
        external
        view
        returns (ConfigTypes.InitMultiAssetVaultParams memory);

    function getBuyAssetAddresses() external view returns (address[] memory);

    function getStrategyParams()
        external
        view
        returns (ConfigTypes.StrategyParams memory);

    function getInitialDepositBalance(
        address depositor
    ) external view returns (uint256);

    function getDepositorBuyAmounts(
        address depositor
    ) external view returns (uint256[] memory);

    function getUpdateFrequencyTimestamp() external view returns (uint256);

    function lastUpdateOf(address depositor) external view returns (uint256);
}
