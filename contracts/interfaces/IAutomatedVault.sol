// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";

interface IAutomatedVault {
    function setLastUpdate() external;

    function getInitMultiAssetVaultParams()
        external
        view
        returns (ConfigTypes.InitMultiAssetVaultParams memory);

    function getBuyAssetAddresses() external view returns (address[] memory);

    function getStrategyParams()
        external
        view
        returns (ConfigTypes.StrategyParams memory);
}
