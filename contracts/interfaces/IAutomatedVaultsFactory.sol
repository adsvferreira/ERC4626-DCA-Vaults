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

    function getVaultAddress(uint256 i) external view returns (address);

    function getAllVaults(
        uint256 limit,
        uint256 startAfter
    ) external view returns (address[] memory);

    function getUserVaults(
        address user
    ) external view returns (address[] memory);

    function getAllVaultsPerStrategyWorker(
        address strategyWorker
    ) external view returns (address[] memory);
}
