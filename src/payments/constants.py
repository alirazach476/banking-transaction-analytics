"""Domain constants for the synthetic payment lifecycle. All data is synthetic."""

from __future__ import annotations

SETTLEMENT_CURRENCY = "USD"

# country -> (currency, sampling weight for merchants)
COUNTRIES: dict[str, tuple[str, float]] = {
    "US": ("USD", 0.60),
    "GB": ("GBP", 0.08),
    "DE": ("EUR", 0.06),
    "FR": ("EUR", 0.04),
    "CA": ("CAD", 0.06),
    "PK": ("PKR", 0.05),
    "AE": ("AED", 0.04),
    "IN": ("INR", 0.07),
}
CURRENCIES = sorted({c for c, _ in COUNTRIES.values()})

# USD per 1 unit of currency (synthetic anchor values) and daily log-vol
FX_ANCHORS: dict[str, tuple[float, float]] = {
    "USD": (1.0, 0.0),
    "EUR": (1.08, 0.003),
    "GBP": (1.27, 0.003),
    "CAD": (0.74, 0.002),
    "PKR": (0.0036, 0.0008),
    "AED": (0.2723, 0.0002),
    "INR": (0.012, 0.0008),
}

CHANNELS = ["POS Chip", "POS Contactless", "E-commerce", "Mobile Wallet"]
CHANNEL_WEIGHTS = [0.25, 0.30, 0.28, 0.17]
CARD_NOT_PRESENT_CHANNELS = {"E-commerce", "Recurring"}

# lognormal (mu, sigma) of amount in transaction-currency-equivalent USD by category
CATEGORY_AMOUNT = {
    "Grocery": (3.7, 0.7), "Restaurant": (3.3, 0.6), "Fuel": (3.8, 0.4),
    "Retail": (4.0, 0.9), "Travel": (5.3, 1.0), "Healthcare": (4.6, 0.9),
    "Education": (5.2, 0.8), "Entertainment": (3.2, 0.7), "Technology": (4.7, 1.0),
    "Utilities": (4.4, 0.6), "Other": (3.8, 0.9),
}
CATEGORY_WEIGHTS = {
    "Grocery": .18, "Restaurant": .14, "Fuel": .10, "Retail": .16, "Travel": .06,
    "Healthcare": .07, "Education": .05, "Entertainment": .08, "Technology": .06,
    "Utilities": .06, "Other": .04,
}
PROFILE_AMOUNT_MULT = {"Retail": 1.0, "Premium": 2.2, "Business": 3.0, "Student": 0.5}
PROFILE_FREQ_MULT = {"Retail": 1.0, "Premium": 1.3, "Business": 1.8, "Student": 0.7}

DECLINE_REASONS = [
    "INSUFFICIENT_FUNDS", "EXPIRED_CARD", "INVALID_CARD", "SUSPECTED_FRAUD",
    "INCORRECT_SECURITY_INFO", "ISSUER_UNAVAILABLE", "PROCESSING_TIMEOUT",
    "RESTRICTED_TRANSACTION",
]
# base weights for *unforced* declines (EXPIRED_CARD is forced by card expiry)
DECLINE_REASON_WEIGHTS = {
    "INSUFFICIENT_FUNDS": 0.38, "EXPIRED_CARD": 0.0, "INVALID_CARD": 0.04,
    "SUSPECTED_FRAUD": 0.10, "INCORRECT_SECURITY_INFO": 0.10,
    "ISSUER_UNAVAILABLE": 0.08, "PROCESSING_TIMEOUT": 0.07,
    "RESTRICTED_TRANSACTION": 0.08,
}

# "True" data-generating coefficients of the decline logit — documented so the
# statistics / ML modules can be checked against known ground truth.
DECLINE_LOGIT = {
    "intercept": -3.4, "international": 0.6, "card_not_present": 0.5,
    "log10_amount_centered": 0.45, "night": 0.5, "fraud_pattern": 1.5,
}

EVENT_TYPES = [
    "AUTH_REQUEST", "AUTH_RESPONSE", "CLEARING", "SETTLEMENT",
    "REVERSAL", "REFUND", "CHARGEBACK",
]

CHARGEBACK_REASONS = ["FRAUD", "NOT_RECEIVED", "NOT_AS_DESCRIBED", "DUPLICATE_PROCESSING"]

SETTLEMENT_ISSUES = [
    "MISSING", "DUPLICATE", "AMOUNT_MISMATCH", "CURRENCY_MISMATCH", "LATE", "ORPHAN",
]
