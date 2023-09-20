// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Strategy Worker.
 * @author  André Ferreira

  * @dev    VERSION: 1.0
 *          DATE:    2023.08.29
*/

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";
import {ITreasuryVault} from "../interfaces/ITreasuryVault.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IStrategyWorker} from "../interfaces/IStrategyWorker.sol";
import {IUniswapV2Router} from "../interfaces/IUniswapV2Router.sol";
import {PercentageMath} from "../libraries/math/percentageMath.sol";
import {AutomatedVaultERC4626, IERC20} from "./AutomatedVaultERC4626.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract StrategyWorker is IStrategyWorker {
    using SafeERC20 for IERC20;
    using Math for uint256;
    using PercentageMath for uint256;

    uint16 public constant MAX_SLIPPAGE_PERC = 5e1; // 0.5%

    address public dexRouter;
    address public dexMainToken;
    address public controller;

    event StrategyActionExecuted(
        address indexed vault,
        address indexed depositor,
        address tokenIn,
        uint256 tokenInAmount,
        address[] tokensOut,
        uint256[] tokensOutAmounts,
        uint256 feeAmount
    );

    constructor(
        address _dexRouter,
        address _dexMainToken,
        address _controller
    ) {
        dexRouter = _dexRouter;
        dexMainToken = _dexMainToken;
        controller = _controller;
    }

    modifier onlyController() {
        require(msg.sender == controller, "Only controller can call this");
        _;
    }

    function executeStrategyAction(
        address strategyVaultAddress,
        address depositorAddress
    ) external onlyController {
        AutomatedVaultERC4626 strategyVault = AutomatedVaultERC4626(
            strategyVaultAddress
        );

        (
            address depositAsset,
            address[] memory buyAssets,
            uint256[] memory buyAmounts
        ) = _getSwapParams(strategyVault, depositorAddress);

        ConfigTypes.InitMultiAssetVaultParams
            memory initMultiAssetVaultParams = strategyVault
                .getInitMultiAssetVaultParams();

        uint256 actionFeePercentage = initMultiAssetVaultParams
            .treasuryPercentageFeeOnBalanceUpdate;
        address payable protocolTreasuryAddress = initMultiAssetVaultParams
            .treasury;
        uint256 amountToWithdraw;
        uint256[] memory buyAmountsAfterFee;
        uint256 totalFee;

        (
            amountToWithdraw,
            buyAmountsAfterFee,
            totalFee
        ) = _calculateAmountsAfterFee(buyAmounts, actionFeePercentage);

        uint256 totalBuyAmount = amountToWithdraw - totalFee;

        strategyVault.setLastUpdate();
        strategyVault.setLastUpdatePerDepositor(depositorAddress);

        strategyVault.withdraw(
            amountToWithdraw,
            address(this), //receiver
            depositorAddress //owner
        );

        address[2] memory spenders = [dexRouter, protocolTreasuryAddress];
        _ensureApprovedERC20(depositAsset, spenders);

        uint256[] memory swappedAssetAmounts = _swapTokens(
            depositorAddress,
            depositAsset,
            buyAssets,
            buyAmountsAfterFee
        );

        ITreasuryVault(protocolTreasuryAddress).depositERC20(
            totalFee,
            depositAsset
        );

        emit StrategyActionExecuted(
            strategyVaultAddress,
            depositorAddress,
            depositAsset,
            totalBuyAmount,
            buyAssets,
            swappedAssetAmounts,
            totalFee
        );
    }

    function _getSwapParams(
        AutomatedVaultERC4626 strategyVault,
        address depositorAddress
    )
        private
        view
        returns (
            address depositAsset,
            address[] memory buyAssets,
            uint256[] memory buyAmounts
        )
    {
        ConfigTypes.InitMultiAssetVaultParams
            memory initMultiAssetVaultParams = strategyVault
                .getInitMultiAssetVaultParams();
        depositAsset = address(initMultiAssetVaultParams.depositAsset);
        buyAssets = strategyVault.getBuyAssetAddresses();
        buyAmounts = strategyVault.getDepositorBuyAmounts(depositorAddress);
    }

    function _calculateAmountsAfterFee(
        uint256[] memory buyAmounts,
        uint256 actionFeePercentage
    )
        private
        returns (
            uint256 amountToWithdraw,
            uint256[] memory buyAmountsAfterFee,
            uint256 totalFee
        )
    {
        uint256 buyAmountsLength = buyAmounts.length;
        buyAmountsAfterFee = new uint256[](buyAmountsLength);
        for (uint256 i = 0; i < buyAmountsLength; i++) {
            uint256 buyAmount = buyAmounts[i];
            uint256 feeAmount = buyAmount.percentMul(actionFeePercentage);
            totalFee += feeAmount;
            uint256 buyAmountAfterFee = buyAmount - feeAmount;
            buyAmountsAfterFee[i] = buyAmountAfterFee;
            amountToWithdraw += buyAmount;
        }
        require(
            amountToWithdraw > 0,
            "Total buyAmount must be greater than zero"
        );
    }

    function _swapTokens(
        address depositorAddress,
        address depositAsset,
        address[] memory buyAssets,
        uint256[] memory buyAmountsAfterFee
    ) internal returns (uint256[] memory amountsOut) {
        uint256 buyAssetsLength = buyAssets.length;
        amountsOut = new uint256[](buyAssetsLength);
        for (uint256 i = 0; i < buyAssets.length; i++) {
            uint256 amountOut = _swapToken(
                depositorAddress,
                depositAsset,
                buyAssets[i],
                buyAmountsAfterFee[i]
            );
            amountsOut[i] = amountOut;
        }
    }

    function _swapToken(
        address depositorAddress,
        address depositAsset,
        address buyAsset,
        uint256 buyAmountAfterFee
    ) internal returns (uint256 amountOut) {
        IUniswapV2Router dexRouterContract = IUniswapV2Router(dexRouter);

        if (buyAsset != dexMainToken && depositAsset != dexMainToken) {
            address[] memory indirectPath = _getIndirectPath(
                depositAsset,
                buyAsset
            );
            uint256[] memory minAmountsOut = dexRouterContract.getAmountsOut(
                buyAmountAfterFee,
                indirectPath
            );
            uint256 minAmountOut = minAmountsOut[minAmountsOut.length - 1];

            uint256 amountOutMin = minAmountOut.percentMul(
                PercentageMath.PERCENTAGE_FACTOR - MAX_SLIPPAGE_PERC
            );

            uint256[] memory amountsOut = dexRouterContract
                .swapExactTokensForTokens(
                    buyAmountAfterFee,
                    amountOutMin,
                    indirectPath,
                    depositorAddress, // swapped tokens sent directly to vault depositor
                    block.timestamp + 600 // 10 min max to execute
                );
            amountOut = amountsOut[amountsOut.length - 1]; // amounts out contains results from all the pools in the choosen route
        } else {
            address[] memory directPath = _getDirectPath(
                depositAsset,
                buyAsset
            );
            uint256[] memory minAmountsOut = dexRouterContract.getAmountsOut(
                buyAmountAfterFee,
                directPath
            );
            uint256 minAmountOut = minAmountsOut[minAmountsOut.length - 1];

            uint256 amountOutMin = minAmountOut.percentMul(
                PercentageMath.PERCENTAGE_FACTOR - MAX_SLIPPAGE_PERC
            );

            uint256[] memory amountsOut = dexRouterContract
                .swapExactTokensForTokens(
                    buyAmountAfterFee,
                    amountOutMin,
                    directPath,
                    depositorAddress, // swapped tokens sent directly to vault depositor
                    block.timestamp + 600 // 10 min max to execute
                );
            amountOut = amountsOut[amountsOut.length - 1]; // amounts out contains results from all the pools in the choosen route
        }
    }

    function _ensureApprovedERC20(
        address tokenAddress,
        address[2] memory spenders
    ) private {
        IERC20 token = IERC20(tokenAddress);

        for (uint256 i = 0; i < spenders.length; i++) {
            uint256 currentAllowance = token.allowance(
                address(msg.sender),
                spenders[i]
            );
            if (currentAllowance == 0) {
                token.approve(spenders[i], type(uint256).max);
            }
        }
    }

    function _getDirectPath(
        address depositAsset,
        address buyAsset
    ) private pure returns (address[] memory) {
        address[] memory path = new address[](2);
        path[0] = depositAsset;
        path[1] = buyAsset;
        return path;
    }

    function _getIndirectPath(
        address depositAsset,
        address buyAsset
    ) private view returns (address[] memory) {
        address[] memory path = new address[](3);
        path[0] = depositAsset;
        path[1] = dexMainToken;
        path[2] = buyAsset;
        return path;
    }
}
