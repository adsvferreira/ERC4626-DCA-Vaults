// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Deposit Assets Whitelister.
 * @author  André Ferreira
 * @dev    VERSION: 1.0
 *          DATE:    2023.10.04
 */

import {Enums} from "../libraries/types/Enums.sol";
import {Roles} from "../libraries/roles/Roles.sol";
import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IStrategyManager} from "../interfaces/IStrategyManager.sol";
import {PercentageMath} from "../libraries/math/PercentageMath.sol";
import {StrategyUtils} from "../libraries/helpers/StrategyUtils.sol";
import {IPriceFeedsDataConsumer} from "../interfaces/IPriceFeedsDataConsumer.sol";

contract StrategyManager is IStrategyManager, Ownable {
    uint256 public constant SAFETY_FACTORS_PRECISION_MULTIPLIER = 1000;
    uint256 private _MAX_EXPECTED_GAS_UNITS_WEI;

    mapping(Enums.BuyFrequency => uint256)
        private _maxNumberOfActionsPerFrequency;

    mapping(Enums.StrategyTimeLimitsInDays => uint256)
        private _gasCostSafetyFactors;

    mapping(Enums.AssetTypes => mapping(Enums.StrategyTimeLimitsInDays => uint256))
        private _depositTokenPriceSafetyFactors;

    mapping(Enums.BuyFrequency => uint256) private _numberOfDaysPerBuyFrequency;

    address[] private _whitelistedDepositAssetAddresses;
    mapping(address => ConfigTypes.WhitelistedDepositAsset)
        private _whitelistedDepositAssets;

    IPriceFeedsDataConsumer public priceFeedsDataConsumer;

    constructor(address _priceFeedsDataConsumer) {
        _fillNumberOfDaysPerBuyFrequency();
        _fillMaxNumberOfActionsPerFrequencyDefaultMap();
        _fillGasCostSafetyFactorsDefaultMap();
        _fillDepositTokenPriceSafetyFactorsDefaultMap();
        priceFeedsDataConsumer = IPriceFeedsDataConsumer(
            _priceFeedsDataConsumer
        );
    }

    function addWhitelistedDepositAssets(
        ConfigTypes.WhitelistedDepositAsset[] calldata depositAssetsToWhitelist
    ) external onlyOwner {
        uint256 assetsLength = depositAssetsToWhitelist.length;
        for (uint256 i = 0; i < assetsLength; i++) {
            _whitelistedDepositAssets[
                depositAssetsToWhitelist[i].assetAddress
            ] = depositAssetsToWhitelist[i];
            _whitelistedDepositAssetAddresses[i] = depositAssetsToWhitelist[i]
                .assetAddress;
        }
    }

    function deactivateWhitelistedDepositAsset(
        address depositTokenAddress
    ) external onlyOwner {
        _whitelistedDepositAssets[depositTokenAddress].isActive = false;
    }

    function setMaxExpectedGasUnits(
        uint256 maxExpectedGasUnits
    ) external onlyOwner {
        require(
            maxExpectedGasUnits > 0,
            "Max expected gas units value must be greater than zero"
        );
        _MAX_EXPECTED_GAS_UNITS_WEI = maxExpectedGasUnits;
    }

    function setGasCostSafetyFactor(
        Enums.StrategyTimeLimitsInDays strategyTimeLimitsInDays,
        uint32 gasCostSafetyFactor
    ) external onlyOwner {
        _gasCostSafetyFactors[strategyTimeLimitsInDays] = gasCostSafetyFactor;
    }

    function setDepositTokenPriceSafetyFactor(
        Enums.AssetTypes assetType,
        Enums.StrategyTimeLimitsInDays strategyTimeLimitsInDays,
        uint32 depositTokenPriceSafetyFactor
    ) external onlyOwner {
        _depositTokenPriceSafetyFactors[assetType][
            strategyTimeLimitsInDays
        ] = depositTokenPriceSafetyFactor;
    }

    function getMaxNumberOfActionsPerFrequency(
        Enums.BuyFrequency buyFrequency
    ) external view returns (uint256) {
        return _maxNumberOfActionsPerFrequency[buyFrequency];
    }

    function getMaxExpectedGasUnits() external view returns (uint256) {
        return _MAX_EXPECTED_GAS_UNITS_WEI;
    }

    function getWhitelistedDepositAssetAddresses()
        external
        view
        returns (address[] memory)
    {
        return _whitelistedDepositAssetAddresses;
    }

    function getWhitelistedDepositAsset(
        address depositAssetAddress
    ) external view returns (ConfigTypes.WhitelistedDepositAsset memory) {
        return _whitelistedDepositAssets[depositAssetAddress];
    }

    function getGasCostSafetyFactor(
        uint256 maxNumberOfStrategyActions,
        Enums.BuyFrequency buyFrequency
    ) external view returns (uint256) {
        uint256 buyFrequencyInDays = _numberOfDaysPerBuyFrequency[buyFrequency];
        uint256 maxNumberOfDays = buyFrequencyInDays *
            maxNumberOfStrategyActions;
        uint256 maxNumberOfDaysAllowed = _maxNumberOfActionsPerFrequency[
            buyFrequency
        ];
        require(
            maxNumberOfDays <= maxNumberOfDaysAllowed,
            "Max number of actions exceeds the limit"
        );
        if (maxNumberOfDaysAllowed <= 30) {
            return _gasCostSafetyFactors[Enums.StrategyTimeLimitsInDays.THIRTY];
        }
        if (maxNumberOfDaysAllowed <= 180) {
            return
                _gasCostSafetyFactors[
                    Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
                ];
        }
        if (maxNumberOfDaysAllowed <= 180) {
            return
                _gasCostSafetyFactors[
                    Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
                ];
        }
        if (maxNumberOfDaysAllowed <= 365) {
            return
                _gasCostSafetyFactors[
                    Enums.StrategyTimeLimitsInDays.THREE_HUNDRED_AND_SIXTY_FIVE
                ];
        }
    }

    function getDepositTokenPriceSafetyFactor(
        Enums.AssetTypes assetType,
        uint256 maxNumberOfStrategyActions,
        Enums.BuyFrequency buyFrequency
    ) external view returns (uint256) {
        uint256 buyFrequencyInDays = _numberOfDaysPerBuyFrequency[buyFrequency];
        uint256 maxNumberOfDays = buyFrequencyInDays *
            maxNumberOfStrategyActions;
        uint256 maxNumberOfDaysAllowed = _maxNumberOfActionsPerFrequency[
            buyFrequency
        ];
        require(
            maxNumberOfDays <= maxNumberOfDaysAllowed,
            "Max number of actions exceeds the limit"
        );
        if (maxNumberOfDaysAllowed <= 30) {
            return
                _depositTokenPriceSafetyFactors[assetType][
                    Enums.StrategyTimeLimitsInDays.THIRTY
                ];
        }
        if (maxNumberOfDaysAllowed <= 180) {
            return
                _depositTokenPriceSafetyFactors[assetType][
                    Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
                ];
        }
        if (maxNumberOfDaysAllowed <= 180) {
            return
                _depositTokenPriceSafetyFactors[assetType][
                    Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
                ];
        }
        if (maxNumberOfDaysAllowed <= 365) {
            return
                _depositTokenPriceSafetyFactors[assetType][
                    Enums.StrategyTimeLimitsInDays.THREE_HUNDRED_AND_SIXTY_FIVE
                ];
        }
    }

    function simulateMinDepositValue(
        ConfigTypes.WhitelistedDepositAsset calldata whitelistedDepositAsset,
        uint256[] memory buyPercentages,
        Enums.BuyFrequency buyFrequency,
        uint256 treasuryPercentageFeeOnBalanceUpdate
    ) external view returns (uint256 minDepositValue) {
        uint256 buyPercentagesSum = StrategyUtils.buyPercentagesSum(
            buyPercentages
        );
        uint256 nativeTokenParsedPrice = uint256(
            priceFeedsDataConsumer.getNativeTokenDataFeedLatestPriceParsed()
        );
        uint256 depositTokenParsedPrice = uint256(
            priceFeedsDataConsumer.getTokenDataFeedLatestPriceParsed(
                whitelistedDepositAsset.oracleAddress
            )
        );
        uint256 gasPriceWei;
        assembly {
            gasPriceWei := gasprice()
        }
        uint256 gasPriceEth = gasPriceWei / (10 ** 18);
        uint256 maxExpectedGas = this.getMaxExpectedGasUnits();
        uint256 maxNumberOfStrategyActions = StrategyUtils
            .calculateStrategyMaxNumberOfActions(buyPercentagesSum);
        uint256 gasCostSafetyFactor = this.getGasCostSafetyFactor(
            maxNumberOfStrategyActions,
            buyFrequency
        );
        uint256 depositTokenPriceSafetyFactor = this
            .getDepositTokenPriceSafetyFactor(
                whitelistedDepositAsset.assetType,
                maxNumberOfStrategyActions,
                buyFrequency
            );
        // prettier-ignore
        minDepositValue = nativeTokenParsedPrice * PercentageMath.PERCENTAGE_FACTOR * 
        ((maxExpectedGas * maxNumberOfStrategyActions * gasPriceEth * gasCostSafetyFactor) 
        / (treasuryPercentageFeeOnBalanceUpdate * depositTokenPriceSafetyFactor));
    }

    function _fillNumberOfDaysPerBuyFrequency() private {
        _numberOfDaysPerBuyFrequency[Enums.BuyFrequency.FIFTEEN_MIN] = 1; //TEST ONLY -> TODO: DELETE BEFORE PROD DEPLOYMENT
        _numberOfDaysPerBuyFrequency[Enums.BuyFrequency.DAILY] = 1;
        _numberOfDaysPerBuyFrequency[Enums.BuyFrequency.WEEKLY] = 7;
        _numberOfDaysPerBuyFrequency[Enums.BuyFrequency.BI_WEEKLY] = 14;
        _numberOfDaysPerBuyFrequency[Enums.BuyFrequency.MONTHLY] = 30;
    }

    function _fillMaxNumberOfActionsPerFrequencyDefaultMap() private {
        _maxNumberOfActionsPerFrequency[Enums.BuyFrequency.FIFTEEN_MIN] = 60; //TEST ONLY -> TODO: DELETE BEFORE PROD DEPLOYMENT
        _maxNumberOfActionsPerFrequency[Enums.BuyFrequency.DAILY] = 60;
        _maxNumberOfActionsPerFrequency[Enums.BuyFrequency.WEEKLY] = 52;
        _maxNumberOfActionsPerFrequency[Enums.BuyFrequency.BI_WEEKLY] = 26;
        _maxNumberOfActionsPerFrequency[Enums.BuyFrequency.MONTHLY] = 12;
    }

    function _fillGasCostSafetyFactorsDefaultMap() private {
        _gasCostSafetyFactors[Enums.StrategyTimeLimitsInDays.THIRTY] = 1000;
        _gasCostSafetyFactors[Enums.StrategyTimeLimitsInDays.NINETY] = 2250;
        _gasCostSafetyFactors[
            Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
        ] = 3060;
        _gasCostSafetyFactors[
            Enums.StrategyTimeLimitsInDays.THREE_HUNDRED_AND_SIXTY_FIVE
        ] = 4000;
    }

    function _fillDepositTokenPriceSafetyFactorsDefaultMap() private {
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.STABLE][
            Enums.StrategyTimeLimitsInDays.THIRTY
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.STABLE][
            Enums.StrategyTimeLimitsInDays.NINETY
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.STABLE][
            Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.STABLE][
            Enums.StrategyTimeLimitsInDays.THREE_HUNDRED_AND_SIXTY_FIVE
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.ETH_BTC][
            Enums.StrategyTimeLimitsInDays.THIRTY
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.ETH_BTC][
            Enums.StrategyTimeLimitsInDays.NINETY
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.ETH_BTC][
            Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.ETH_BTC][
            Enums.StrategyTimeLimitsInDays.THREE_HUNDRED_AND_SIXTY_FIVE
        ] = 1000;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.BLUE_CHIP][
            Enums.StrategyTimeLimitsInDays.THIRTY
        ] = 900;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.BLUE_CHIP][
            Enums.StrategyTimeLimitsInDays.NINETY
        ] = 800;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.BLUE_CHIP][
            Enums.StrategyTimeLimitsInDays.ONE_HUNDRED_AND_EIGHTY
        ] = 650;
        _depositTokenPriceSafetyFactors[Enums.AssetTypes.BLUE_CHIP][
            Enums.StrategyTimeLimitsInDays.THREE_HUNDRED_AND_SIXTY_FIVE
        ] = 500;
    }
}
