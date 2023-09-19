from typing import List, Union
from scripts.backend.dataclasses import StrategyVault
from scripts.backend.helpers import buy_frequency_enum_to_seconds_map
from brownie import config, AutomatedVaultERC4626, AutomatedVaultsFactory, network

factory_address = config["networks"][network.show_active()]["vaults_factory_address"]
vaults_factory_contract = AutomatedVaultsFactory.at(factory_address)


class StrategyFetcher:
    def fetch_vault_addresses(self) -> List[str]:
        number_of_vaults = vaults_factory_contract.allVaultsLength()
        return [vaults_factory_contract.allVaults(i) for i in range(number_of_vaults)]

    def fetch_vaults(
        self,
        vault_addresses: List[str],
        buy_frequency_timestamp: Union[int, None] = None,
    ) -> List[StrategyVault]:
        if buy_frequency_timestamp and buy_frequency_timestamp not in buy_frequency_enum_to_seconds_map.values():
            print("TIMESTAMP CHOSEN IS NOT VALID")
        else:
            vaults_list = []
            for vault_address in vault_addresses:
                vault_contract = AutomatedVaultERC4626.at(vault_address)
                strategy_params = vault_contract.getStrategyParams()
                vault_buy_frequency_timestamp = self.__get_vault_buy_frequency_timestamp(strategy_params)
                if buy_frequency_timestamp and buy_frequency_timestamp != vault_buy_frequency_timestamp:
                    continue
                vault_params = vault_contract.initMultiAssetVaultParams()
                token_addresses_to_buy_length = vault_contract.buyAssetsLength()
                all_depositors_length = vault_contract.allDepositorsLength()
                vault = StrategyVault(
                    address=vault_contract.address,
                    creator=vault_params[3],
                    deposit_token_address=vault_params[6],
                    token_addresses_to_buy=self.__get_token_addresses_to_buy(
                        vault_contract, token_addresses_to_buy_length
                    ),
                    depositor_addresses=self.__get_depositor_addresses(vault_contract, all_depositors_length),
                    buy_frequency_timestamp=vault_buy_frequency_timestamp,
                    last_update_timestamp=vault_contract.lastUpdate(),
                )
                vaults_list.append(vault)
            return vaults_list

    def __get_vault_buy_frequency_timestamp(self, strategy_params: tuple) -> int:
        return buy_frequency_enum_to_seconds_map[strategy_params[1]]

    def __get_token_addresses_to_buy(
        self, vault_contract: AutomatedVaultERC4626, token_addresses_to_buy_length: int
    ) -> List[str]:
        return [vault_contract.buyAssetAddresses(i) for i in range(token_addresses_to_buy_length)]

    def __get_depositor_addresses(self, vault_contract: AutomatedVaultERC4626, all_depositors_length: int) -> List[str]:
        return [vault_contract.allDepositorAddresses(i) for i in range(all_depositors_length)]
