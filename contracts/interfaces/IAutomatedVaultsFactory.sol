// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";

interface IAutomatedVaultsFactory {
    function allVaultsLength() external view returns (uint256);

    function createVault(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            memory initMultiAssetVaultFactoryParams,
        ConfigTypes.StrategyParams calldata strategyParams
    ) external payable returns (address newVaultAddress);

    function allPairsExistForBuyAssets(
        address depositAsset,
        address[] memory buyAssets
    ) external view returns (bool);

    function pairExistsForBuyAsset(
        address depositAsset,
        address buyAsset
    ) external view returns (bool);
}
