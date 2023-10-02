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
import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IAutomatedVault} from "../interfaces/IAutomatedVault.sol";
import {PercentageMath} from "../libraries/math/PercentageMath.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {IERC20Metadata, IERC20, ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

error InvalidParameters();

contract AutomatedVaultERC4626 is ERC4626, AccessControl, IAutomatedVault {
    using Math for uint256;
    using SafeERC20 for IERC20;
    using PercentageMath for uint256;

    uint256 public feesAccruedByCreator;
    uint8 public constant MAX_NUMBER_OF_BUY_ASSETS = 10;

    ConfigTypes.InitMultiAssetVaultParams public initMultiAssetVaultParams;
    ConfigTypes.StrategyParams public strategyParams;

    address[] public buyAssetAddresses;
    uint256 public buyAssetsLength;
    /**
     * @dev Note: Removing entries from dynamic arrays can be gas-expensive.
     * The `allDepositorAddresses` array stores all users who have deposited funds in this vault,
     * even if they have already withdrawn their entire balance. Use `balanceOf` to check individual balances.
     */
    address[] private _allDepositorAddresses;
    uint256 public allDepositorsLength;

    /**
     * @notice Periodic buy amounts are calculated as a percentage of the first deposit.
     * A user's first deposit is detected when their vault balance is zero.
     * To adjust the absolute amounts swapped periodically, withdraw the entire balance and deposit a different amount.
     */
    mapping(address depositor => uint256) private _initialDepositBalances;
    mapping(address depositor => uint256[]) private _depositorBuyAmounts;
    mapping(Enums.BuyFrequency => uint256) private _updateFrequencies;
    mapping(address depositor => uint256) private _lastUpdatePerDepositor;

    event CreatorFeeTransfered(
        address indexed vault,
        address indexed depositor,
        address indexed creator,
        uint256 shares
    );

    /**
     * @dev Attempted to deposit more assets than the max amount for `receiver`.
     */
    error ERC4626ExceededMaxDeposit(
        address receiver,
        uint256 assets,
        uint256 max
    );

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
        require(msg.sender == _initMultiAssetVaultParams.factory, "FORBIDDEN");
        _validateInputs(
            _initMultiAssetVaultParams.buyAssets,
            _strategyParams.buyPercentages
        );
        _setupRole(Roles.STRATEGY_WORKER, _strategyParams.strategyWorker);
        initMultiAssetVaultParams = _initMultiAssetVaultParams;
        _populateBuyAssetsData(_initMultiAssetVaultParams);
        strategyParams = _strategyParams;
        initMultiAssetVaultParams.isActive = false;
        _fillUpdateFrequenciesMap();
    }

    /** @dev See {IERC4626-deposit}. */
    function deposit(
        uint256 assets,
        address receiver
    ) public override(ERC4626) returns (uint256) {
        uint256 maxAssets = maxDeposit(receiver);
        if (assets > maxAssets) {
            revert ERC4626ExceededMaxDeposit(receiver, assets, maxAssets);
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
        return initMultiAssetVaultParams;
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
        for (uint256 i = 0; i < buyAssetsLength; i++) {
            totalPeriodicBuyAmount += _depositorBuyAmounts[depositor][i];
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
        require(
            buyAssets.length <= uint256(MAX_NUMBER_OF_BUY_ASSETS),
            "MAX_NUMBER_OF_BUY_ASSETS exceeded"
        );
        // Check if both arrays have the same length
        require(
            buyPercentages.length == buyAssets.length,
            "buyPercentages and buyAssets arrays must have the same length"
        );
    }

    function _populateBuyAssetsData(
        ConfigTypes.InitMultiAssetVaultParams memory _initMultiAssetVaultParams
    ) private {
        buyAssetsLength = _initMultiAssetVaultParams.buyAssets.length;
        for (uint256 i = 0; i < buyAssetsLength; i++) {
            buyAssetAddresses.push(
                address(_initMultiAssetVaultParams.buyAssets[i])
            );
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
        if (receiver == initMultiAssetVaultParams.creator) {
            if (balanceOf(receiver) == 0 && shares > 0) {
                _allDepositorAddresses.push(receiver);
                allDepositorsLength += 1;
                _initialDepositBalances[receiver] = shares;
                _updateDepositorBuyAmounts(receiver);
            }
            _mint(receiver, shares);
        } else {
            // if deposit is not from vault creator, a fee will be removed
            // from depositor and added to creator balance
            uint256 creatorPercentage = initMultiAssetVaultParams
                .creatorPercentageFeeOnDeposit;
            uint256 depositorPercentage = PercentageMath.PERCENTAGE_FACTOR -
                creatorPercentage;
            uint256 creatorShares = shares.percentMul(creatorPercentage);
            uint256 depositorShares = shares.percentMul(depositorPercentage);

            emit CreatorFeeTransfered(
                address(this),
                initMultiAssetVaultParams.creator,
                receiver,
                creatorShares
            );

            if (balanceOf(receiver) == 0 && depositorShares > 0) {
                _allDepositorAddresses.push(receiver);
                allDepositorsLength += 1;
                _initialDepositBalances[receiver] = depositorShares;
                _updateDepositorBuyAmounts(receiver);
            }
            _mint(receiver, depositorShares);

            if (
                balanceOf(initMultiAssetVaultParams.creator) == 0 &&
                creatorShares > 0
            ) {
                _allDepositorAddresses.push(initMultiAssetVaultParams.creator);
                allDepositorsLength += 1;
                _initialDepositBalances[
                    initMultiAssetVaultParams.creator
                ] = creatorShares;
                _updateDepositorBuyAmounts(initMultiAssetVaultParams.creator);
            }
            feesAccruedByCreator += creatorShares;
            _mint(initMultiAssetVaultParams.creator, creatorShares);
        }
        // Activates vault after 1st deposit
        if (initMultiAssetVaultParams.isActive == false && shares > 0) {
            initMultiAssetVaultParams.isActive = true;
        }
    }

    function _updateDepositorBuyAmounts(address depositor) internal {
        uint256 initialDepositBalance = _initialDepositBalances[depositor];
        for (uint256 i = 0; i < buyAssetsLength; i++) {
            _depositorBuyAmounts[depositor].push(
                initialDepositBalance.percentMul(
                    strategyParams.buyPercentages[i]
                )
            );
        }
    }

    function getAllDepositorAddresses(
        uint256 limit,
        uint256 startAfter
    ) public view returns (address[] memory) {
        if (limit + startAfter > _allDepositorAddresses.length) {
            revert InvalidParameters(
                "limit + startAfter exceed the number of vaults."
            );
        }
        address[] memory allDepositors_ = new address[](limit);
        uint256 counter = 0; // This is needed to copy from a storage array to a memory array.
        for (uint256 i = startAfter; i < startAfter + limit; i++) {
            allDepositors_[counter] = _allDepositorAddresses[i];
            counter += 1;
        }
        return allDepositors_;
    }
}
