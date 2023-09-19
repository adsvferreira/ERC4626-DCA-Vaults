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

    address[] public allVaults;
    mapping(address => address[]) public getUserVaults;

    IUniswapV2Factory uniswapV2Factory;

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
        return allVaults.length;
    }

    function createVault(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            memory initMultiAssetVaultFactoryParams,
        ConfigTypes.StrategyParams calldata strategyParams
    ) external payable returns (address newVaultAddress) {
        require(
            msg.value >= treasuryFixedFeeOnVaultCreation,
            "ETHER SENT MUST COVER VAULT CREATION FEE"
        );

        _validateCreateVaultInputs(
            initMultiAssetVaultFactoryParams,
            strategyParams.buyPercentages
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
        allVaults.push(newVaultAddress);
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
        address _depositAsset,
        address[] memory _buyAssets
    ) external view returns (bool) {
        for (uint256 i = 0; i < _buyAssets.length; i++) {
            if (
                this.pairExistsForBuyAsset(_depositAsset, _buyAssets[i]) ==
                false
            ) {
                return false;
            }
        }
        return true;
    }

    function pairExistsForBuyAsset(
        address _depositAsset,
        address _buyAsset
    ) external view returns (bool) {
        require(
            _depositAsset != _buyAsset,
            "BUY ASSET LIST CONTAINS DEPOSIT ASSET"
        );
        if (uniswapV2Factory.getPair(_depositAsset, _buyAsset) != address(0)) {
            return true;
        }
        if (uniswapV2Factory.getPair(_buyAsset, dexMainToken) != address(0)) {
            return true;
        }
        return false;
    }

    function _validateCreateVaultInputs(
        ConfigTypes.InitMultiAssetVaultFactoryParams
            memory initMultiAssetVaultFactoryParams,
        uint256[] memory buyPercentages
    ) private view {
        require(
            address(initMultiAssetVaultFactoryParams.depositAsset) !=
                address(0),
            "ZERO_ADDRESS"
        );
        if (initMultiAssetVaultFactoryParams.depositAsset != dexMainToken) {
            require(
                uniswapV2Factory.getPair(
                    initMultiAssetVaultFactoryParams.depositAsset,
                    dexMainToken
                ) != address(0),
                "SWAP PATH BETWEEN DEPOSIT ASSET AND DEX MAIN TOKEN NOT FOUND"
            );
        }
        require(
            this.allPairsExistForBuyAssets(
                initMultiAssetVaultFactoryParams.depositAsset,
                initMultiAssetVaultFactoryParams.buyAssets
            ),
            "SWAP PATH NOT FOUND FOR AT LEAST 1 BUY ASSET"
        );
        require(
            _buyPercentagesSum(buyPercentages) <=
                PercentageMath.PERCENTAGE_FACTOR,
            "BUY PERCENTAGES SUM IS GT 100"
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
        getUserVaults[creator].push(newVault);
    }

    function _buyPercentagesSum(
        uint256[] memory buyPercentages
    ) private pure returns (uint256 buyPercentagesSum) {
        for (uint256 i = 0; i < buyPercentages.length; i++) {
            require(buyPercentages[i] > 0, "Buy percentage must be gt zero");
            buyPercentagesSum += buyPercentages[i];
        }
    }
}
