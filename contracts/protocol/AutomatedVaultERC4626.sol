// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Automated ERC-4626 Vault Factory.
 * @author  André Ferreira
 * @notice  See the following for the full EIP-4626 specification https://eips.ethereum.org/EIPS/eip-4626.
 * @notice  See the following for the full EIP-4626 openzeppelin implementation https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC4626.sol.

  * @dev    VERSION: 1.0
 *          DATE:    2023.08.13
*/

import {Roles} from "../libraries/roles/Roles.sol";
import {Enums} from "../libraries/types/Enums.sol";
import {Errors} from "../libraries/types/Errors.sol";
import {Events} from "../libraries/types/Events.sol";
import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";
import {IAutomatedVault} from "../interfaces/IAutomatedVault.sol";
import {IStrategyWorker} from "../interfaces/IStrategyWorker.sol";
import {PercentageMath} from "../libraries/math/PercentageMath.sol";
import {IStrategyManager} from "../interfaces/IStrategyManager.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IAutomatedVaultsFactory} from "../interfaces/IAutomatedVaultsFactory.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {IERC20Metadata, IERC20, ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract AutomatedVaultERC4626 is ERC4626, AccessControl, IAutomatedVault {
    using SafeERC20 for IERC20;
    using PercentageMath for uint256;

    uint256 public feesAccruedByCreator;
    uint8 public constant MAX_NUMBER_OF_BUY_ASSETS = 5;

    ConfigTypes.StrategyParams private strategyParams;
    ConfigTypes.InitMultiAssetVaultParams private initMultiAssetsVaultParams;

    IStrategyWorker private _strategyWorker;
    IStrategyManager private _strategyManager;

    uint256 public buyAssetsLength;
    address[] public buyAssetAddresses;
    /**
     * @dev Note: Removing entries from dynamic arrays can be gas-expensive.
     * The `getDepositorAddress` array stores all users who have deposited funds in this vault,
     * even if they have already withdrawn their entire balance. Use `balanceOf` to check individual balances.
     */
    address[] public getDepositorAddress;
    uint256 public allDepositorsLength;

    /**
     * @notice Periodic buy amounts are calculated as a percentage of the first deposit.
     * A user's first deposit is detected when their vault balance is zero.
     * To adjust the absolute amounts swapped periodically, withdraw the entire balance and deposit a different amount.
     */
    mapping(address depositor => uint256) private _initialDepositBalances;
    mapping(address depositor => uint256) private _lastUpdatePerDepositor;
    mapping(address depositor => uint256[]) private _depositorBuyAmounts;
    mapping(Enums.BuyFrequency => uint256) private _updateFrequencies;

    constructor(
        ConfigTypes.InitMultiAssetVaultParams memory _initMultiAssetVaultParams,
        ConfigTypes.StrategyParams memory _strategyParams
    )
        ERC4626(_initMultiAssetVaultParams.depositAsset)
        ERC20(
            _initMultiAssetVaultParams.name,
            _initMultiAssetVaultParams.symbol
        )
    {
        if (msg.sender != _initMultiAssetVaultParams.factory) {
            revert Errors.Forbidden("Not factory");
        }
        _validateInputs(
            _initMultiAssetVaultParams.buyAssets,
            _strategyParams.buyPercentages
        );
        _setupRole(Roles.STRATEGY_WORKER, _strategyParams.strategyWorker);
        initMultiAssetsVaultParams = _initMultiAssetVaultParams;
        _populateBuyAssetsData(_initMultiAssetVaultParams);
        strategyParams = _strategyParams;
        _strategyWorker = IStrategyWorker(_strategyParams.strategyWorker);
        _strategyManager = IStrategyManager(_strategyParams.strategyManager);
        initMultiAssetsVaultParams.isActive = false;
        _fillUpdateFrequenciesMap();
    }

    /** @dev See {IERC4626-deposit}. */
    function deposit(
        uint256 assets,
        address receiver
    ) public override(ERC4626) returns (uint256) {
        ConfigTypes.WhitelistedDepositAsset
            memory whitelistedDepositAsset = _strategyManager
                .getWhitelistedDepositAsset(asset());
        uint256 minDepositValue = _strategyManager.simulateMinDepositValue(
            whitelistedDepositAsset,
            strategyParams.buyPercentages,
            strategyParams.buyFrequency,
            initMultiAssetsVaultParams.treasuryPercentageFeeOnBalanceUpdate,
            uint256(decimals())
        );
        if (assets < minDepositValue) {
            revert Errors.InvalidParameters(
                "Deposit amount lower that the minimum allowed"
            );
        }
        uint256 shares = previewDeposit(assets);
        _deposit(_msgSender(), receiver, assets, shares);
        return shares;
    }

    function setLastUpdatePerDepositor(
        address depositor
    ) external onlyRole(Roles.STRATEGY_WORKER) {
        _lastUpdatePerDepositor[depositor] = block.timestamp;
    }

    function getInitMultiAssetVaultParams()
        external
        view
        returns (ConfigTypes.InitMultiAssetVaultParams memory)
    {
        return initMultiAssetsVaultParams;
    }

    function getBuyAssetAddresses() external view returns (address[] memory) {
        return buyAssetAddresses;
    }

    function getStrategyParams()
        external
        view
        returns (ConfigTypes.StrategyParams memory)
    {
        return strategyParams;
    }

    function getInitialDepositBalance(
        address depositor
    ) external view virtual returns (uint256) {
        return _initialDepositBalances[depositor];
    }

    function getDepositorBuyAmounts(
        address depositor
    ) external view virtual returns (uint256[] memory) {
        return _depositorBuyAmounts[depositor];
    }

    function getDepositorTotalPeriodicBuyAmount(
        address depositor
    ) external view returns (uint256 totalPeriodicBuyAmount) {
        if (_depositorBuyAmounts[depositor].length == 0) {
            return 0;
        }
        uint256 _buyAssetsLength = buyAssetsLength;
        for (uint256 i; i < _buyAssetsLength; ) {
            totalPeriodicBuyAmount += _depositorBuyAmounts[depositor][i];
            unchecked {
                ++i;
            }
        }
    }

    function getUpdateFrequencyTimestamp()
        external
        view
        virtual
        returns (uint256)
    {
        return _updateFrequencies[strategyParams.buyFrequency];
    }

    function lastUpdateOf(
        address depositor
    ) external view virtual returns (uint256) {
        return _lastUpdatePerDepositor[depositor];
    }

    function getBatchDepositorAddresses(
        uint256 limit,
        uint256 startAfter
    ) public view returns (address[] memory) {
        uint256 depositorsLength = getDepositorAddress.length;
        if (startAfter >= depositorsLength) {
            revert Errors.InvalidParameters("Invalid interval");
        }
        uint256 counter; // This is needed to copy from a storage array to a memory array.
        uint256 startLimit;
        uint256 outputLen;
        if (startAfter + limit <= depositorsLength) {
            startLimit = startAfter + limit;
            outputLen = limit;
        } else {
            startLimit = depositorsLength;
            outputLen = depositorsLength - startAfter;
        }
        address[] memory allDepositors = new address[](outputLen);
        for (uint256 i = startAfter; i < startLimit; ) {
            allDepositors[counter] = getDepositorAddress[i];
            unchecked {
                ++i;
                ++counter;
            }
        }
        return allDepositors;
    }

    function _fillUpdateFrequenciesMap() private {
        _updateFrequencies[Enums.BuyFrequency.FIFTEEN_MIN] = 900; //TEST ONLY -> TODO: DELETE BEFORE PROD DEPLOYMENT
        _updateFrequencies[Enums.BuyFrequency.DAILY] = 86400;
        _updateFrequencies[Enums.BuyFrequency.WEEKLY] = 604800;
        _updateFrequencies[Enums.BuyFrequency.BI_WEEKLY] = 1209600;
        _updateFrequencies[Enums.BuyFrequency.MONTHLY] = 2630016;
    }

    function _validateInputs(
        IERC20[] memory buyAssets,
        uint256[] memory buyPercentages
    ) private pure {
        // Check if max number of deposited assets was not exceeded
        if (buyAssets.length > uint256(MAX_NUMBER_OF_BUY_ASSETS)) {
            revert Errors.InvalidParameters(
                "MAX_NUMBER_OF_BUY_ASSETS exceeded"
            );
        }
        // Check if both arrays have the same length
        if (buyPercentages.length != buyAssets.length) {
            revert Errors.InvalidParameters(
                "buyPercentages and buyAssets arrays must have the same length"
            );
        }
    }

    function _populateBuyAssetsData(
        ConfigTypes.InitMultiAssetVaultParams memory _initMultiAssetVaultParams
    ) private {
        buyAssetsLength = _initMultiAssetVaultParams.buyAssets.length;
        uint256 _buyAssetsLength = buyAssetsLength;
        for (uint256 i; i < _buyAssetsLength; ) {
            buyAssetAddresses.push(
                address(_initMultiAssetVaultParams.buyAssets[i])
            );
            unchecked {
                ++i;
            }
        }
    }

    /**
     * @dev Attempts to fetch the asset decimals. A return value of false indicates that the attempt failed in some way.
     */
    function _originalTryGetAssetDecimals(
        IERC20 asset_
    ) private view returns (bool, uint8) {
        (bool success, bytes memory encodedDecimals) = address(asset_)
            .staticcall(abi.encodeCall(IERC20Metadata.decimals, ()));
        if (success && encodedDecimals.length >= 32) {
            uint256 returnedDecimals = abi.decode(encodedDecimals, (uint256));
            if (returnedDecimals <= type(uint8).max) {
                return (true, uint8(returnedDecimals));
            }
        }
        return (false, 0);
    }

    /**
     * @dev Deposit/mint common workflow.
     */
    function _deposit(
        address caller,
        address receiver,
        uint256 assets,
        uint256 shares
    ) internal override {
        // **************************************** ERC4262 ****************************************
        // If _asset is ERC777, `transferFrom` can trigger a reentrancy BEFORE the transfer happens through the
        // `tokensToSend` hook. On the other hand, the `tokenReceived` hook, that is triggered after the transfer,
        // calls the vault, which is assumed not malicious.
        //
        // Conclusion: we need to do the transfer before we mint so that any reentrancy would happen before the
        // assets are transferred and before the shares are minted, which is a valid state.
        // slither-disable-next-line reentrancy-no-eth
        // **************************************** CUSTOM ****************************************
        // After underlying transfer and before vault lp mint _afterUnderlyingTransferHook was added
        // where vault creator fee logic is implemented
        address depositAsset = asset();
        SafeERC20.safeTransferFrom(
            IERC20(depositAsset),
            caller,
            address(this),
            assets
        );
        _afterUnderlyingTransferHook(receiver, shares);
        emit Deposit(caller, receiver, assets, shares);
    }

    function _afterUnderlyingTransferHook(
        address receiver,
        uint256 shares
    ) internal {
        address creator = initMultiAssetsVaultParams.creator;
        if (receiver == creator) {
            if (balanceOf(receiver) == 0 && shares > 0) {
                getDepositorAddress.push(receiver);
                ++allDepositorsLength;
                _initialDepositBalances[receiver] = shares;
                _updateDepositorBuyAmounts(receiver);
            }
            _mint(receiver, shares);
        } else {
            // if deposit is not from vault creator, a fee will be removed
            // from depositor and added to creator balance
            uint256 creatorPercentage = initMultiAssetsVaultParams
                .creatorPercentageFeeOnDeposit;
            uint256 depositorPercentage = PercentageMath.PERCENTAGE_FACTOR -
                creatorPercentage;
            uint256 creatorShares = shares.percentMul(creatorPercentage);
            uint256 depositorShares = shares.percentMul(depositorPercentage);

            emit Events.CreatorFeeTransfered(
                address(this),
                creator,
                receiver,
                creatorShares
            );

            if (balanceOf(receiver) == 0 && depositorShares > 0) {
                getDepositorAddress.push(receiver);
                ++allDepositorsLength;
                _initialDepositBalances[receiver] = depositorShares;
                _updateDepositorBuyAmounts(receiver);
            }
            _mint(receiver, depositorShares);

            if (balanceOf(creator) == 0 && creatorShares > 0) {
                getDepositorAddress.push(creator);
                ++allDepositorsLength;
                _initialDepositBalances[creator] = creatorShares;
                _updateDepositorBuyAmounts(creator);
            }
            feesAccruedByCreator += creatorShares;
            _mint(creator, creatorShares);
        }
        // Activates vault after 1st deposit
        if (!initMultiAssetsVaultParams.isActive && shares > 0) {
            initMultiAssetsVaultParams.isActive = true;
        }
    }

    function _updateDepositorBuyAmounts(address depositor) internal {
        uint256 initialDepositBalance = _initialDepositBalances[depositor];
        uint256 _buyAssetsLength = buyAssetsLength;
        for (uint256 i; i < _buyAssetsLength; ) {
            _depositorBuyAmounts[depositor].push(
                initialDepositBalance.percentMul(
                    strategyParams.buyPercentages[i]
                )
            );
            unchecked {
                ++i;
            }
        }
    }
}
