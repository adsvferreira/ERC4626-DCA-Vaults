// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Automated ERC-4626 Vault.
 * @author  André Ferreira
 * @dev    VERSION: 1.0
 *          DATE:    2023.08.15
 */

import {Enums} from "../libraries/types/Enums.sol";
import {Errors} from "../libraries/types/Errors.sol";
import {Events} from "../libraries/types/Events.sol";
import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";
import {PercentageMath} from "../libraries/math/PercentageMath.sol";
import {IStrategyManager} from "../interfaces/IStrategyManager.sol";
import {StrategyUtils} from "../libraries/helpers/StrategyUtils.sol";
import {IUniswapV2Factory} from "../interfaces/IUniswapV2Factory.sol";
import {AutomatedVaultERC4626, IERC20} from "./AutomatedVaultERC4626.sol";
import {IAutomatedVaultsFactory} from "../interfaces/IAutomatedVaultsFactory.sol";

contract AutomatedVaultsFactory is IAutomatedVaultsFactory {
    address payable public treasury;
    address public dexMainToken;
    uint256 public treasuryFixedFeeOnVaultCreation; // AMOUNT IN NATIVE TOKEN CONSIDERING ALL DECIMALS
    uint256 public creatorPercentageFeeOnDeposit; // ONE_TEN_THOUSANDTH_PERCENT units (1 = 0.01%)
    uint256 public treasuryPercentageFeeOnBalanceUpdate; // ONE_TEN_THOUSANDTH_PERCENT units (1 = 0.01%)

    address[] public getVaultAddress;
    mapping(address => address[]) private _userVaults;
    mapping(address => address[]) _vaultsPerStrategyWorker;

    IUniswapV2Factory public uniswapV2Factory;
    IStrategyManager public strategyManager;

    constructor(
        address _uniswapV2Factory,
        address _dexMainToken,
        address payable _treasury,
        address _strategyManager,
        uint256 _treasuryFixedFeeOnVaultCreation,
        uint256 _creatorPercentageFeeOnDeposit,
        uint256 _treasuryPercentageFeeOnBalanceUpdate
    ) {
        treasury = _treasury;
        dexMainToken = _dexMainToken;
        treasuryFixedFeeOnVaultCreation = _treasuryFixedFeeOnVaultCreation;
        creatorPercentageFeeOnDeposit = _creatorPercentageFeeOnDeposit;
        treasuryPercentageFeeOnBalanceUpdate = _treasuryPercentageFeeOnBalanceUpdate;
        uniswapV2Factory = IUniswapV2Factory(_uniswapV2Factory);
        strategyManager = IStrategyManager(_strategyManager);
    }

    function allVaultsLength() external view returns (uint256) {
        return getVaultAddress.length;
    }

    function createVault(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            calldata initMultiAssetVaultFactoryParams,
        ConfigTypes.StrategyParams calldata strategyParams
    ) external payable returns (address newVaultAddress) {
        if (msg.value < treasuryFixedFeeOnVaultCreation) {
            revert Errors.InvalidTxEtherAmount(
                "Ether sent must cover vault creation fee"
            );
        }

        _validateCreateVaultInputs(
            initMultiAssetVaultFactoryParams,
            strategyParams
        );

        // SEND CREATION FEE TO PROTOCOL TREASURY
        (bool success, ) = treasury.call{value: msg.value}("");
        if (!success) {
            revert Errors.EtherTransferFailed(
                "Fee transfer to treasury address failed."
            );
        }
        emit Events.TreasuryFeeTransfered(
            address(msg.sender),
            treasuryFixedFeeOnVaultCreation
        );

        ConfigTypes.InitMultiAssetVaultParams
            memory initMultiAssetVaultParams = _buildInitMultiAssetVaultParams(
                initMultiAssetVaultFactoryParams
            );

        // CREATE NEW STRATEGY VAULT
        AutomatedVaultERC4626 newVault = new AutomatedVaultERC4626(
            initMultiAssetVaultParams,
            strategyParams
        );
        newVaultAddress = address(newVault);
        getVaultAddress.push(newVaultAddress);
        _vaultsPerStrategyWorker[strategyParams.strategyWorker].push(
            newVaultAddress
        );
        _addUserVault(initMultiAssetVaultParams.creator, newVaultAddress);
        emit Events.VaultCreated(
            initMultiAssetVaultParams.creator,
            address(initMultiAssetVaultParams.depositAsset),
            initMultiAssetVaultFactoryParams.buyAssets,
            newVaultAddress,
            strategyParams.buyPercentages,
            strategyParams.buyFrequency
        );
    }

    function allPairsExistForBuyAssets(
        address depositAsset,
        address[] calldata buyAssets
    ) external view returns (bool) {
        uint256 _buyAssetsLength = buyAssets.length;
        for (uint256 i; i < _buyAssetsLength; ) {
            if (
                this.pairExistsForBuyAsset(depositAsset, buyAssets[i]) == false
            ) {
                return false;
            }
            unchecked {
                ++i;
            }
        }
        return true;
    }

    function pairExistsForBuyAsset(
        address depositAsset,
        address buyAsset
    ) external view returns (bool) {
        if (depositAsset == buyAsset) {
            revert Errors.InvalidParameters(
                "Buy asset list contains deposit asset"
            );
        }

        if (
            uniswapV2Factory.getPair(depositAsset, buyAsset) != address(0) ||
            uniswapV2Factory.getPair(buyAsset, dexMainToken) != address(0)
        ) {
            return true;
        }
        return false;
    }

    function getAllVaultsPerStrategyWorker(
        address strategyWorker
    ) external view returns (address[] memory) {
        return _vaultsPerStrategyWorker[strategyWorker];
    }

    function getBatchVaults(
        uint256 limit,
        uint256 startAfter
    ) public view returns (address[] memory) {
        uint256 vaultAddressLength = getVaultAddress.length;
        if (startAfter >= vaultAddressLength) {
            revert Errors.InvalidParameters("Invalid interval");
        }
        uint256 counter; // This is needed to copy from a storage array to a memory array.
        uint256 startLimit;
        uint256 outputLen;
        if (startAfter + limit <= vaultAddressLength) {
            startLimit = startAfter + limit;
            outputLen = limit;
        } else {
            startLimit = vaultAddressLength;
            outputLen = vaultAddressLength - startAfter;
        }
        address[] memory vaults = new address[](outputLen);
        for (uint256 i = startAfter; i < startLimit; ) {
            vaults[counter] = getVaultAddress[i];
            unchecked {
                ++i;
                ++counter;
            }
        }
        return vaults;
    }

    function getUserVaults(
        address user
    ) external view returns (address[] memory) {
        return _userVaults[user];
    }

    function _validateCreateVaultInputs(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            memory initMultiAssetVaultFactoryParams,
        ConfigTypes.StrategyParams memory strategyParams
    ) private view {
        if (
            address(initMultiAssetVaultFactoryParams.depositAsset) == address(0)
        ) {
            revert Errors.InvalidParameters(
                "Deposit address cannot be zero address"
            );
        }
        if (address(strategyParams.strategyWorker) == address(0)) {
            revert Errors.InvalidParameters(
                "strategyWorker address cannot be zero address"
            );
        }
        if (
            !strategyManager
                .getWhitelistedDepositAsset(
                    initMultiAssetVaultFactoryParams.depositAsset
                )
                .isActive
        ) {
            revert Errors.InvalidParameters(
                "Deposit address is not whitelisted"
            );
        }
        if (initMultiAssetVaultFactoryParams.depositAsset != dexMainToken) {
            if (
                uniswapV2Factory.getPair(
                    initMultiAssetVaultFactoryParams.depositAsset,
                    dexMainToken
                ) == address(0)
            ) {
                revert Errors.SwapPathNotFound(
                    "Swap path between deposit asset and dex main token not found"
                );
            }
        }
        if (
            !this.allPairsExistForBuyAssets(
                initMultiAssetVaultFactoryParams.depositAsset,
                initMultiAssetVaultFactoryParams.buyAssets
            )
        ) {
            revert Errors.SwapPathNotFound(
                "Swap path not found for at least 1 buy asset"
            );
        }
        uint256 buyPercentagesSum = StrategyUtils.buyPercentagesSum(
            strategyParams.buyPercentages
        );
        if (buyPercentagesSum > PercentageMath.PERCENTAGE_FACTOR) {
            revert Errors.InvalidParameters("Buy percentages sum is gt 100");
        }
        if (
            _calculateStrategyMaxNumberOfActions(buyPercentagesSum) >
            strategyManager.getMaxNumberOfActionsPerFrequency(
                strategyParams.buyFrequency
            )
        ) {
            revert Errors.InvalidParameters(
                "Max number of actions exceeds the limit"
            );
        }
    }

    function _buildInitMultiAssetVaultParams(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            memory _initMultiAssetVaultFactoryParams
    )
        private
        view
        returns (
            ConfigTypes.InitMultiAssetVaultParams
                memory _initMultiAssetVaultParams
        )
    {
        _initMultiAssetVaultParams = ConfigTypes.InitMultiAssetVaultParams(
            _initMultiAssetVaultFactoryParams.name,
            _initMultiAssetVaultFactoryParams.symbol,
            treasury,
            payable(msg.sender),
            address(this),
            false,
            IERC20(_initMultiAssetVaultFactoryParams.depositAsset),
            _wrapBuyAddressesIntoIERC20(
                _initMultiAssetVaultFactoryParams.buyAssets
            ),
            creatorPercentageFeeOnDeposit,
            treasuryPercentageFeeOnBalanceUpdate
        );
        return _initMultiAssetVaultParams;
    }

    function _wrapBuyAddressesIntoIERC20(
        address[] memory buyAddresses
    ) private pure returns (IERC20[] memory iERC20instances) {
        uint256 _buyAddressesLength = buyAddresses.length;
        iERC20instances = new IERC20[](_buyAddressesLength);
        for (uint256 i; i < _buyAddressesLength; ) {
            iERC20instances[i] = IERC20(buyAddresses[i]);
            unchecked {
                ++i;
            }
        }
        return iERC20instances;
    }

    function _addUserVault(address creator, address newVault) private {
        if (creator == address(0)) {
            revert Errors.InvalidParameters(
                "Null Address is not a valid creator address"
            );
        }
        if (newVault == address(0)) {
            revert Errors.InvalidParameters(
                "Null Address is not a valid newVault address"
            );
        }
        // 2 vaults can't the same address, tx would revert at vault instantiation
        _userVaults[creator].push(newVault);
    }

    /**
     * @dev Note: division by zero needs to be previously checked
     */
    function _calculateStrategyMaxNumberOfActions(
        uint256 sumOfBuyPercentages
    ) internal pure returns (uint256 maxNumberOfActions) {
        maxNumberOfActions =
            PercentageMath.PERCENTAGE_FACTOR /
            sumOfBuyPercentages;
    }
}
