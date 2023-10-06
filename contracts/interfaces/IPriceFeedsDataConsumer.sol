// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

interface IPriceFeedsDataConsumer {
    function getDataFeedLatestPriceAndDecimals(
        address oracleAddress
    ) external view returns (uint256, uint256);

    function getNativeTokenDataFeedLatestPriceAndDecimals()
        external
        view
        returns (uint256, uint256);

    function getTokenDataFeedLatestPriceParsed(
        address oracleAddress
    ) external view returns (int256 tokenParsedPrice);

    function getNativeTokenDataFeedLatestPriceParsed()
        external
        view
        returns (int256 nativeTokenParsedPrice);
}
