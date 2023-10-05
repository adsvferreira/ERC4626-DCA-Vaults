// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

interface IPriceFeedsDataConsumer {
    function getDataFeedLatestPrice(
        address oracleAddress
    ) external view returns (int256);

    function getNativeTokenDataFeedLatestPriceAndDecimals()
        external
        view
        returns (int256, uint8);

    function getTokenDataFeedLatestPriceParsed(
        address oracleAddress
    ) external view returns (int256 tokenParsedPrice);

    function getNativeTokenDataFeedLatestPriceParsed()
        external
        view
        returns (int256 nativeTokenParsedPrice);
}
