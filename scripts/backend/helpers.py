event_vault_creation = "VaultCreated"

buy_frequency_enum_to_seconds_map = {
    0: 60,  # TODO: Change After Testing -> This one should be 86400 (DAILY)
    1: 604800,  # WEEKLY
    2: 1209600,  # BI_WEEKLY
    3: 2630016,  # MONTHLY (Assumes average of 30.44 days in month)
}

CONSOLE_SEPARATOR = (
    "--------------------------------------------------------------------------"
)
