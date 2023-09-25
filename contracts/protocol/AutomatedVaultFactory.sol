// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Automated ERC-4626 Vault.
 * @author  André Ferreira
 * @dev    VERSION: 1.0
 *          DATE:    2023.08.15
 */

import {Enums} from "../libraries/types/Enums.sol";
import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";
import {PercentageMath} from "../libraries/math/percentageMath.sol";
import {IUniswapV2Factory} from "../interfaces/IUniswapV2Factory.sol";
import {AutomatedVaultERC4626, IERC20} from "./AutomatedVaultERC4626.sol";
import {IAutomatedVaultsFactory} from "../interfaces/IAutomatedVaultsFactory.sol";

error InvalidParameters(string message);

contract AutomatedVaultsFactory is IAutomatedVaultsFactory {
    event VaultCreated(
        address indexed creator,
        address indexed depositAsset,
        address[] buyAssets,
        address vaultAddress,
        uint256[] buyPercentages,
        Enums.BuyFrequency buyFrequency,
        Enums.StrategyType strategyType
    );
    event TreasuryFeeTransfered(address creator, uint256 amount);

    address payable public treasury;
    address public dexMainToken;
    uint256 public treasuryFixedFeeOnVaultCreation; // AMOUNT IN NATIVE TOKEN CONSIDERING ALL DECIMALS
    uint256 public creatorPercentageFeeOnDeposit; // ONE_TEN_THOUSANDTH_PERCENT units (1 = 0.01%)
    uint256 public treasuryPercentageFeeOnBalanceUpdate; // ONE_TEN_THOUSANDTH_PERCENT units (1 = 0.01%)

    address[] private _allVaults;
    mapping(address => address[]) private _userVaults;

    IUniswapV2Factory public uniswapV2Factory;

    constructor(
        address _uniswapV2Factory,
        address _dexMainToken,
        address payable _treasury,
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
    }

    function allVaultsLength() external view returns (uint256) {
        return _allVaults.length;
    }

    function createVault(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            memory initMultiAssetVaultFactoryParams,
        ConfigTypes.StrategyParams calldata strategyParams
    ) external payable returns (address newVaultAddress) {
        require(
            msg.value >= treasuryFixedFeeOnVaultCreation,
            "Ether sent must cover vault creation fee"
        );

        _validateCreateVaultInputs(
            initMultiAssetVaultFactoryParams,
            strategyParams
        );

        // SEND CREATION FEE TO PROTOCOL TREASURY
        (bool success, ) = treasury.call{value: msg.value}("");
        require(success, "Fee transfer to treasury address failed.");
        emit TreasuryFeeTransfered(
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
        _allVaults.push(newVaultAddress);
        _addUserVault(initMultiAssetVaultParams.creator, newVaultAddress);
        emit VaultCreated(
            initMultiAssetVaultParams.creator,
            address(initMultiAssetVaultParams.depositAsset),
            initMultiAssetVaultFactoryParams.buyAssets,
            newVaultAddress,
            strategyParams.buyPercentages,
            strategyParams.buyFrequency,
            strategyParams.strategyType
        );
    }

    function allPairsExistForBuyAssets(
        address depositAsset,
        address[] memory buyAssets
    ) external view returns (bool) {
        for (uint256 i = 0; i < buyAssets.length; i++) {
            if (
                this.pairExistsForBuyAsset(depositAsset, buyAssets[i]) == false
            ) {
                return false;
            }
        }
        return true;
    }

    function pairExistsForBuyAsset(
        address depositAsset,
        address buyAsset
    ) external view returns (bool) {
        require(
            depositAsset != buyAsset,
            "Buy asset list contains deposit asset"
        );
        if (uniswapV2Factory.getPair(depositAsset, buyAsset) != address(0)) {
            return true;
        }
        if (uniswapV2Factory.getPair(buyAsset, dexMainToken) != address(0)) {
            return true;
        }
        return false;
    }

    function getVaultAddress(
        uint256 i
    ) external view virtual returns (address) {
        return _allVaults[i];
    }

    function _validateCreateVaultInputs(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            memory initMultiAssetVaultFactoryParams,
        ConfigTypes.StrategyParams memory strategyParams
    ) private view {
        require(
            address(initMultiAssetVaultFactoryParams.depositAsset) !=
                address(0),
            "Deposit address cannot be zero address"
        );
        if (initMultiAssetVaultFactoryParams.depositAsset != dexMainToken) {
            require(
                uniswapV2Factory.getPair(
                    initMultiAssetVaultFactoryParams.depositAsset,
                    dexMainToken
                ) != address(0),
                "Swap path between deposit asser and dex main token not found"
            );
        }
        require(
            this.allPairsExistForBuyAssets(
                initMultiAssetVaultFactoryParams.depositAsset,
                initMultiAssetVaultFactoryParams.buyAssets
            ),
            "Swap path not found for at least 1 buy asset"
        );
        require(
            _buyPercentagesSum(strategyParams.buyPercentages) <=
                PercentageMath.PERCENTAGE_FACTOR,
            "Buy percentages sum is gt 100"
        );
        require(
            address(strategyParams.strategyWorker) != address(0),
            "strategyWorker address cannot be zero address"
        );
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
        uint256 buyAddressesLength = buyAddresses.length;
        iERC20instances = new IERC20[](buyAddressesLength);
        for (uint256 i = 0; i < buyAddressesLength; i++) {
            iERC20instances[i] = IERC20(buyAddresses[i]);
        }
        return iERC20instances;
    }

    function _addUserVault(address creator, address newVault) private {
        require(
            creator != address(0),
            "Null Address is not a valid creator address"
        );
        require(
            newVault != address(0),
            "Null Address is not a valid newVault address"
        );
        // 2 vaults can't the same address, tx would revert at vault instantiation
        _userVaults[creator].push(newVault);
    }

    function _buyPercentagesSum(
        uint256[] memory buyPercentages
    ) private pure returns (uint256 buyPercentagesSum) {
        for (uint256 i = 0; i < buyPercentages.length; i++) {
            require(buyPercentages[i] > 0, "Buy percentage must be gt zero");
            buyPercentagesSum += buyPercentages[i];
        }
    }

    function getAllVaults(
        uint256 limit,
        uint256 startAfter
    ) public view returns (address[] memory) {
        if (limit + startAfter > _allVaults.length) {
            revert InvalidParameters(
                "limit + startAfter exceed the number of vaults."
            );
        }
        address[] memory vaults = new address[](limit);
        uint256 counter = 0; // This is needed to copy from a storage array to a memory array.
        for (uint256 i = startAfter; i < startAfter + limit; i++) {
            vaults[counter] = _allVaults[i];
            counter += 1;
        }
        return vaults;
    }

    function getUserVaults(
        address user
    ) public view returns (address[] memory) {
        return _userVaults[user];
    }
}
