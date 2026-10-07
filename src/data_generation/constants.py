"""Domain constants and realistic distributions for synthetic NovaBank data."""

CUSTOMER_TYPES = ["Retail", "Premium", "Business", "Student"]
CUSTOMER_TYPE_WEIGHTS = [0.55, 0.15, 0.15, 0.15]

CUSTOMER_STATUSES = ["Active", "Inactive", "Suspended", "Closed"]
CUSTOMER_STATUS_WEIGHTS = [0.78, 0.12, 0.05, 0.05]

ACCOUNT_TYPES = ["Checking", "Savings", "Business", "Student", "Premium Savings"]
ACCOUNT_TYPE_WEIGHTS = [0.40, 0.30, 0.12, 0.10, 0.08]

ACCOUNT_STATUSES = ["Active", "Inactive", "Frozen", "Closed"]
ACCOUNT_STATUS_WEIGHTS = [0.85, 0.08, 0.03, 0.04]

BRANCH_TYPES = ["Flagship", "Standard", "Express", "Rural"]
BRANCH_TYPE_WEIGHTS = [0.10, 0.55, 0.25, 0.10]
BRANCH_STATUSES = ["Open", "Closed", "Renovating"]
BRANCH_STATUS_WEIGHTS = [0.92, 0.05, 0.03]

MERCHANT_CATEGORIES = [
    "Grocery",
    "Restaurant",
    "Fuel",
    "Retail",
    "Travel",
    "Healthcare",
    "Education",
    "Entertainment",
    "Technology",
    "Utilities",
    "Other",
]
MERCHANT_CATEGORY_WEIGHTS = [
    0.18, 0.14, 0.10, 0.16, 0.06, 0.07, 0.05, 0.08, 0.06, 0.06, 0.04
]

CARD_TYPES = ["Debit", "Credit", "Prepaid"]
CARD_TYPE_WEIGHTS = [0.60, 0.30, 0.10]
CARD_STATUSES = ["Active", "Inactive", "Blocked", "Expired"]
CARD_STATUS_WEIGHTS = [0.82, 0.08, 0.05, 0.05]

TRANSACTION_TYPES = [
    "Deposit",
    "Withdrawal",
    "Transfer",
    "Payment",
    "Refund",
    "Fee",
    "Interest",
    "Bill Payment",
]
# Payments and withdrawals dominate retail banking volume
TRANSACTION_TYPE_WEIGHTS = [0.12, 0.18, 0.12, 0.28, 0.04, 0.06, 0.04, 0.16]

TRANSACTION_STATUSES = ["Completed", "Pending", "Failed", "Reversed"]
TRANSACTION_STATUS_WEIGHTS = [0.88, 0.04, 0.05, 0.03]

CHANNELS = [
    "ATM",
    "Branch",
    "Mobile App",
    "Internet Banking",
    "POS",
    "Online",
]
CHANNEL_WEIGHTS = [0.18, 0.12, 0.30, 0.15, 0.15, 0.10]

TRANSFER_TYPES = ["Internal", "Domestic", "International"]
TRANSFER_TYPE_WEIGHTS = [0.55, 0.35, 0.10]

CURRENCIES = ["USD", "EUR", "GBP", "CAD"]
CURRENCY_WEIGHTS = [0.85, 0.07, 0.05, 0.03]

GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"]
GENDER_WEIGHTS = [0.48, 0.48, 0.02, 0.02]

# Synthetic regions / cities (fictional-friendly real city names for realism)
REGIONS = {
    "Northeast": ["New York", "Boston", "Philadelphia", "Newark", "Buffalo"],
    "Southeast": ["Atlanta", "Miami", "Charlotte", "Orlando", "Tampa"],
    "Midwest": ["Chicago", "Detroit", "Minneapolis", "Columbus", "Indianapolis"],
    "Southwest": ["Dallas", "Houston", "Phoenix", "Austin", "San Antonio"],
    "West": ["Los Angeles", "San Francisco", "Seattle", "Portland", "Denver"],
}
COUNTRY = "United States"

# Amount distribution parameters by transaction type (lognormal-ish via mean/std of log)
AMOUNT_PARAMS = {
    "Deposit": {"mean": 6.5, "sigma": 1.2, "min": 10, "max": 50000},
    "Withdrawal": {"mean": 4.5, "sigma": 0.8, "min": 20, "max": 2000},
    "Transfer": {"mean": 6.0, "sigma": 1.4, "min": 50, "max": 100000},
    "Payment": {"mean": 3.8, "sigma": 0.9, "min": 5, "max": 2000},
    "Refund": {"mean": 3.5, "sigma": 1.0, "min": 5, "max": 1500},
    "Fee": {"mean": 2.5, "sigma": 0.6, "min": 1, "max": 100},
    "Interest": {"mean": 2.0, "sigma": 1.0, "min": 0.01, "max": 500},
    "Bill Payment": {"mean": 4.8, "sigma": 0.7, "min": 20, "max": 3000},
}

# Customer behavior profile multipliers applied to amount / frequency
BEHAVIOR_PROFILES = {
    "Retail": {"amount_mult": 1.0, "freq_mult": 1.0},
    "Premium": {"amount_mult": 2.5, "freq_mult": 1.3},
    "Business": {"amount_mult": 4.0, "freq_mult": 1.8},
    "Student": {"amount_mult": 0.45, "freq_mult": 0.7},
}

# Dirty status variants intentionally injected into source data
STATUS_VARIANTS = {
    "Completed": ["Completed", "completed", "COMPLETED", "Complete"],
    "Pending": ["Pending", "pending", "PENDING"],
    "Failed": ["Failed", "failed", "FAILED", "Fail"],
    "Reversed": ["Reversed", "reversed", "REVERSED"],
    "Active": ["Active", "active", "ACTIVE"],
    "Inactive": ["Inactive", "inactive", "INACTIVE"],
}

ANOMALY_TYPES = [
    "high_amount",
    "high_frequency",
    "rapid_transactions",
    "unusual_location",
    "night_activity",
    "multiple_failures",
    "sudden_behavior_change",
]

FICTIONAL_COUNTRIES = [
    "NovaLand",
    "Aetheria",
    "Cascadia Republic",
    "Valoria",
    "Meridia",
]
