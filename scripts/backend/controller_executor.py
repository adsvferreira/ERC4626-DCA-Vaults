from brownie import Controller, config, network, accounts

BACKEND_BOT_WALLET = accounts.add(config["wallets"]["from_key_1"])
controller_address = config["networks"][network.show_active()]["controller_address"]
controller_contract = Controller.at(controller_address)
worker_address = config["networks"][network.show_active()]["worker_address"]


class ControllerExecutor:
    def trigger_strategy_action(
        self, vault_address: str, depositor_address: str
    ) -> object:
        return controller_contract.triggerStrategyAction(
            worker_address,
            vault_address,
            depositor_address,
            {"from": BACKEND_BOT_WALLET},
        )
