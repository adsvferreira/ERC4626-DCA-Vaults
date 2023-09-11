from brownie import web3
from brownie import config, AutomatedVaultsFactory, network

factory_address = config["networks"][network.show_active()]["vaults_factory_address"]
vaults_factory_contract = AutomatedVaultsFactory.at(factory_address)


class EventListener:
    def __init__(self):
        self.block_number = web3.eth.blockNumber

    # returns the new vaults addresses
    def event_listener_vaults_update(self) -> list[str]:
        event_filter = vaults_factory_contract.events.VaultCreated.createFilter(
            fromBlock=self.block_number
        )
        entries = event_filter.get_all_entries()
        self.block_number = web3.eth.blockNumber

        return [entry.args.vaultAddress for entry in entries]
