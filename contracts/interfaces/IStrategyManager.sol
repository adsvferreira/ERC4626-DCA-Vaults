// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

import {Enums} from "../libraries/types/Enums.sol";
import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";

interface IStrategyManager {
    function addWhitelistedDepositAssets(
        ConfigTypes.WhitelistedDepositAsset[] calldata depositAssetsToWhitelist
    ) external;

    function deactivateWhitelistedDepositAsset(
        address depositTokenAddress
    ) external;

    function setMaxExpectedGasUnits(uint256 maxExpectedGasUnits) external;

    function setGasCostSafetyFactor(
        Enums.StrategyTimeLimitsInDays strategyTimeLimitsInDays,
        uint32 gasCostSafetyFactor
    ) external;

    function setDepositTokenPriceSafetyFactor(
        Enums.AssetTypes assetType,
        Enums.StrategyTimeLimitsInDays strategyTimeLimitsInDays,
        uint32 depositTokenPriceSafetyFactor
    ) external;

    function getMaxNumberOfActionsPerFrequency(
        Enums.BuyFrequency buyFrequency
    ) external view returns (uint256);

    function getMaxExpectedGasUnits() external view returns (uint256);

    function getWhitelistedDepositAssetAddresses()
        external
        view
        returns (address[] memory);

    function getWhitelistedDepositAsset(
        address depositAssetAddress
    ) external view returns (ConfigTypes.WhitelistedDepositAsset memory);

    function getGasCostSafetyFactor(
        uint256 maxNumberOfStrategyActions,
        Enums.BuyFrequency buyFrequency
    ) external view returns (uint256);

    function getDepositTokenPriceSafetyFactor(
        Enums.AssetTypes assetType,
        uint256 maxNumberOfStrategyActions,
        Enums.BuyFrequency buyFrequency
    ) external view returns (uint256);

    function simulateMinDepositValue(
        ConfigTypes.WhitelistedDepositAsset calldata whitelistedDepositAsset,
        uint256[] memory buyPercentages,
        Enums.BuyFrequency buyFrequency,
        uint256 treasuryPercentageFeeOnBalanceUpdate
    ) external view returns (uint256 minDepositValue);
}
