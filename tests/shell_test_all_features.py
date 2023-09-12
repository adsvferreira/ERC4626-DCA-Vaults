from brownie import accounts, config, network
from brownie import (
    AutomatedVaultsFactory,
    AutomatedVaultERC4626,
    TreasuryVault,
    StrategyWorker,
    Controller,
)

# Goerli testing addresses (old):
# Treasury: 0x964FF99Ff53DbAaCE609eB2dA09953F9b9CAeec3
# Factory: 0x3bBc24e06285E4229d25c1a7b1BcaB9482F1288c
# Vault: 0x205eb5673D825ED50Be3FcF4532A8201bdcDE4A7

# Arbitrum mainnet testing addresses (old):
# Treasury: 0xA87c2b2dB83E849Ba1FFcf40C8F56F4984CFbC69
# Factory: 0x87899933E5E989Ae4F028FD09D77E47F8912D229
# Vault: 0x35A816b3b2E53d64d9a135fe1f4323e59A73645b

# dev_wallet = accounts[0]
dev_wallet = accounts.add(config["wallets"]["from_key_1"])
# dev_wallet_2 = accounts.add(config["wallets"]["from_key_2"])

# # MAINNET ADDRESSES:
# usdce_address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
# vault_name = "weth/wbtc vault"
# vault_symbol = "WETH/WBTC"
# weth_address = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
# wbtc_address = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"

# ARBITRUM MAINNET ADDRESSES (arbitrum-main-fork):
vault_name = "weth/arb vault"
vault_symbol = "WETH/ARB"
usdce_address = "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8"
weth_address = config["networks"][network.show_active()]["dex_main_token_address"]
wbtc_address = "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f"
arb_address = "0x912ce59144191c1204e64559fe8253a0e49e6548"
lon_address = "0x55678cd083fcdc2947a0df635c93c838c89454a3"
dex_router_address = config["networks"][network.show_active()]["dex_router_address"]  # ARBITRUM Sushi
dex_factory_address = config["networks"][network.show_active()]["dex_factory_address"]  # ARBITRUM Sushi


treasury_fixed_fee_on_vault_creation = 100_000_000_000_000  # 0.001 ETH
creator_percentage_fee_on_deposit = 25  # 0.25%
treasury_percentage_fee_on_balance_update = 25  # 0.25%

# PROTOCOL TREASURY
tx1 = TreasuryVault.deploy({"from": dev_wallet})  # owner must be protocol EOA
# TreasuryVault.deploy({'from': dev_wallet}, publish_source=true)
treasury_vault = TreasuryVault[-1]
treasury_address = treasury_vault.address

# CONTROLLER
tx2 = Controller.deploy({"from": dev_wallet})
controller = Controller[-1]
controller_address = controller.address

# STRATEGY WORKER
tx3 = StrategyWorker.deploy(dex_router_address, weth_address, controller_address, {"from": dev_wallet})
strategy_worker = StrategyWorker[-1]
strategy_worker_address = strategy_worker.address

# AutomatedVaultsFactory.deploy(treasury_address,treasury_fixed_fee_on_vault_creation, creator_percentage_fee_on_deposit, treasury_percentage_fee_on_balance_update, {'from': dev_wallet}, publish_source=true)
tx4 = AutomatedVaultsFactory.deploy(
    dex_factory_address,
    weth_address,
    treasury_address,
    treasury_fixed_fee_on_vault_creation,
    creator_percentage_fee_on_deposit,
    treasury_percentage_fee_on_balance_update,
    {"from": dev_wallet},
)

vaults_factory = AutomatedVaultsFactory[-1]

# Test initual vaults length
vaults_factory.allVaultsLength()

init_vault_from_factory_params = (
    vault_name,
    vault_symbol,
    usdce_address,
    [weth_address, arb_address],
)
strategy_params = ([100_0, 100_0], 0, 0, strategy_worker_address)  # Amounts in USDC
# Remix formated params:
# ["weth/wbtc vault", "WETH/WBTC", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", ["0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"]]
# [[1000000000000000000,10000000],0,0]

tx5 = vaults_factory.createVault(
    init_vault_from_factory_params,
    strategy_params,
    {"from": dev_wallet, "value": 100_000_000_000_000},
)

protocol_treasury_balance = treasury_vault.balance()
print("TREASURY BALANCE: ", protocol_treasury_balance)
print("ALL VAULTS LENGTH: ", vaults_factory.allVaultsLength())
print("WALLET STRATEGIES", vaults_factory.getUserVaults(dev_wallet.address, 0))

created_strategy_vault_address = vaults_factory.allVaults(0)
created_strategy_vault = AutomatedVaultERC4626.at(created_strategy_vault_address)

print("INITIAL STRATEGY BALANCE", created_strategy_vault.balanceOf(dev_wallet))
print("INIT VAULT PARAMS:", created_strategy_vault.initMultiAssetVaultParams())
print("VAULT STRATEGY PARAMS:", created_strategy_vault.strategyParams())

usdc = Contract.from_explorer(usdce_address)
usdc_dev_balance = usdc.balanceOf(dev_wallet)
print("USDC DEV BALANCE:", usdc_dev_balance)

# APROVE ERC-20
tx6 = usdc.approve(created_strategy_vault_address, 100_000, {"from": dev_wallet})
# tx2.wait(1)  # Wait for 1 confirmation

# CREATOR DEPOSIT
tx7 = created_strategy_vault.deposit(20_000, dev_wallet.address, {"from": dev_wallet})
created_strategy_vault.balanceOf(dev_wallet)
created_strategy_vault.totalSupply()
created_strategy_vault.allDepositorsLength()
created_strategy_vault.allDepositorAddresses(0)

# WITHDRAW
tx8 = created_strategy_vault.withdraw(10000, dev_wallet, dev_wallet, {"from": dev_wallet})
created_strategy_vault.balanceOf(dev_wallet)
created_strategy_vault.totalSupply()

# APROVE ERC-20
tx9 = usdc.approve(created_strategy_vault_address, 3_000_000, {"from": dev_wallet_2})

# NON-CREATOR DEPOSIT
tx10 = created_strategy_vault.deposit(300_000, dev_wallet_2.address, {"from": dev_wallet_2})
created_strategy_vault.balanceOf(dev_wallet_2)
created_strategy_vault.balanceOf(dev_wallet)
created_strategy_vault.allDepositorsLength()
created_strategy_vault.allDepositorAddresses(0)
created_strategy_vault.allDepositorAddresses(1)

# WITHDRAW PROTOCOL TREASURY BALANCE (OWNER)
tx11 = treasury_vault.withdrawNative(protocol_treasury_balance, {"from": dev_wallet})
print("TREASURY BALANCE: ", treasury_vault.balance())

# TEST STRATEGY WORKER
created_strategy_vault.balanceOf(dev_wallet)
created_strategy_vault.balanceOf(dev_wallet_2)

# USER NEEDS TO GIVE UNLIMITED ALLOWANCE TO WORKER FOR USING VAULT LP BALANCES
tx12 = created_strategy_vault.approve(strategy_worker_address, 9_999_999_999_999_999_999, {"from": dev_wallet_2})

weth = Contract.from_explorer(weth_address)
arb = Contract.from_explorer(arb_address)
print("VAULT DEPOSITOR BALANCES BEFORE ACTION:")
print(f"WETH: {weth.balanceOf(dev_wallet_2)}")
print(f"ARB: {arb.balanceOf(dev_wallet_2)}")

# EXECUTE STRATEGY ACTION FOR dev_wallet_2
tx13 = controller.triggerStrategyAction(
    strategy_worker_address,
    created_strategy_vault_address,
    dev_wallet_2,
    {"from": dev_wallet},
)
print("VAULT DEPOSITOR BALANCES AFTER ACTION:")
print(f"WETH: {weth.balanceOf(dev_wallet_2)}")
print(f"ARB: {arb.balanceOf(dev_wallet_2)}")

# STRATEGY VAULT CREATION FAILED DUE TO PATH NOT FOUND
init_vault_from_factory_params = (
    "invalid strategy",
    "ERROR",
    usdce_address,
    [weth_address, lon_address],
)
strategy_params = ([100_000, 100_000], 0, 0, strategy_worker_address)  # Amounts in USDC

tx14 = vaults_factory.createVault(
    init_vault_from_factory_params,
    strategy_params,
    {"from": dev_wallet, "value": 1_000_000_000_000_000},
)


# usdc = Contract.from_explorer(usdce_address)
# usdc_dev_balance = usdc.balanceOf(dev_wallet_2)
# # vaults_factory_address = "0x87899933E5E989Ae4F028FD09D77E47F8912D229"
# # factory = Contract.from_abi("AutomatedVaultsFactory", vaults_factory_address, factory_abi)
# tx0=AutomatedVaultsFactory.deploy(treasury_address,treasury_fixed_fee_on_vault_creation, creator_percentage_fee_on_deposit, treasury_percentage_fee_on_balance_update, {'from': dev_wallet})

# vaults_factory = AutomatedVaultsFactory[-1]

# init_vault_from_factory_params=(vault_name, vault_symbol, usdce_address, [weth_address, wbtc_address])
# strategy_params=([1_000_000_000_000_000_000, 10_000_000], 0, 0)

# tx1=factory.createVault(init_vault_from_factory_params, strategy_params, {'from':dev_wallet, "value":1_000_000_000_000_000})
# created_strategy_vault_address = factory.allVaults(1)
# created_strategy_vault = AutomatedVaultERC4626.at(created_strategy_vault_address)
# # created_strategy_vault = Contract.from_abi("AutomatedVaultERC4626", created_strategy_vault_address, vault_abi)
