"""Fixed XBRL vocabulary for results filings (design doc 8.1).

Element names follow the BSE Ind-AS results taxonomy (prefix ``in-bse-fin``); integrated filings
(``in-capmkt``, since March 2025) use the same names. Banks and insurers file in their regulators'
formats (RBI, IRDAI general and life) with different element sets, each in its own table here.
NBFCs file the Ind-AS layout (Schedule III Division III) and use the Ind-AS names (seen on Bajaj
Finance).

PHASE 0: confirm every name below against real instance files (open question 22.1). Names marked
``# verify`` were taken from the taxonomy's conventions, not yet from a sampled file. Unmarked
Ind-AS names were seen in the 2026-10-13 spike (Ind-AS_entry_point_2020-03-31.xsd, one company).
"""

# Logical name -> candidate element local-names, first match wins.
INDAS: dict[str, tuple[str, ...]] = {
    "revenue": ("RevenueFromOperations",),
    "other_income": ("OtherIncome",),
    "total_income": ("Income", "TotalIncome"),  # verify TotalIncome (Income seen)
    "total_expenses": ("Expenses", "TotalExpenses"),  # verify TotalExpenses (Expenses seen)
    "finance_costs": ("FinanceCosts",),
    "depreciation": ("DepreciationDepletionAndAmortisationExpense",),
    # Both names are used (L&T, KIMS and about 2,400 other Ind-AS filings tag ExceptionalItems).
    "exceptional_items": ("ExceptionalItemsBeforeTax", "ExceptionalItems"),
    # A line after exceptional items and before tax in the Ind-AS layout (Alletec, Q3 FY26).
    "extraordinary_items": ("ExtraordinaryItems",),
    "pbt": ("ProfitBeforeTax",),
    "tax": ("TaxExpense",),
    "pat_continuing": ("ProfitLossForPeriodFromContinuingOperations",),
    "pat": ("ProfitLossForPeriod",),
    "eps_basic": ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",),
    "total_assets": ("Assets",),
    "equity_and_liabilities": ("EquityAndLiabilities",),
    "total_equity": ("Equity",),
    "total_liabilities": ("Liabilities",),
    "borrowings_noncurrent": ("BorrowingsNoncurrent",),
    "cfo": ("CashFlowsFromUsedInOperatingActivities",),
    # NBFCs (Division III) tag interest income apart from fees (FeesAndCommissionIncome): Bajaj
    # Finance, September 2026; 79 of 84 Ind-AS lenders tag it (June 2026). For a lender, finance
    # costs are its interest expense.
    "interest_income": ("InterestEarned",),
    "interest_expense": ("FinanceCosts",),
    # Expected-credit-loss provisions (Bajaj Finance, September 2026): left out of the core
    # pre-provision margin that fee finance shows (glance.py).
    "impairment": ("ImpairmentOnFinancialInstruments",),
}

# Banks: RBI format. Interest earned + other income = total income; total income - expenditure
# (excluding provisions) - provisions + exceptional items = PBT. Seen on HDFC Bank and SBI
# integrated filings, March and June 2026 quarters, both of which tie out.
BANKING: dict[str, tuple[str, ...]] = {
    "revenue": ("InterestEarned",),
    "other_income": ("OtherIncome",),
    "total_income": ("Income",),
    "interest_expended": ("InterestExpended",),
    "operating_expenses": ("OperatingExpenses",),
    "total_expenses": ("ExpenditureExcludingProvisionsAndContingencies",),
    "operating_profit": ("OperatingProfitBeforeProvisionAndContingencies",),
    "provisions": ("ProvisionsOtherThanTaxAndContingencies",),
    "exceptional_items": ("ExceptionalItems",),
    "extraordinary_items": (),  # RBI format: net of tax, below the profit V2 checks
    "pbt": ("ProfitLossFromOrdinaryActivitiesBeforeTax",),
    "tax": ("TaxExpense",),
    "pat_continuing": ("ProfitLossFromOrdinaryActivitiesAfterTax",),
    "pat": ("ProfitLossForThePeriod",),
    "eps_basic": ("BasicEarningsPerShareAfterExtraordinaryItems",),
    "total_assets": ("Assets",),
    "equity_and_liabilities": ("CapitalAndLiabilities",),
    "total_equity": (),
    "total_liabilities": (),
    "deposits": ("Deposits",),
    "advances": ("Advances",),
    "gross_npa": ("GrossNonPerformingAssets",),
    "net_npa": ("NonPerformingAssets",),
    "interest_income": ("InterestEarned",),
    "interest_expense": ("InterestExpended",),
}
NBFC: dict[str, tuple[str, ...]] = {}  # Ind-AS names apply

# General insurers: IRDAI format. Revenue account: premium earned + investment income + other
# income = operating income; less operating expenses (claims, commission, expenses) = operating
# profit, which moves to the shareholders' account; plus shareholders' investment and other
# income, less non-operating expenses = PBT. Seen on ICICI Lombard (June 2026), which ties out.
INSURANCE: dict[str, tuple[str, ...]] = {
    "revenue": ("PremiumEarned",),
    "gross_premium": ("GrossPremiumsWritten",),
    "net_premium": ("NetPremiumWritten",),
    "investment_income": ("IncomeFromInvestmentsNet",),
    "other_income": ("OtherIncome",),
    "total_income": ("OperatingIncome",),
    "total_expenses": ("OperatingExpenses",),
    "operating_profit": ("OperatingProfitOrLoss",),
    "claims_incurred": ("IncurredClaims",),
    "shareholders_investment_income": ("ShareholdersAccountIncomeFromInvestments",),
    "shareholders_other_income": ("ShareholdersAccountOtherIncome",),
    "non_operating_expenses": ("NonOperatingExpense",),
    # Reinsurers move part of the profit to reserves before PBT (GIC Re, every quarter).
    "transfer_to_reserves": ("TransferToReserves",),
    "interest_income": (),  # not lenders: no interest ratios
    "interest_expense": (),
    "exceptional_items": (),
    "extraordinary_items": (),
    "pbt": ("ProfitOrLossBeforeTax",),
    "tax": ("ProvisionForTax",),
    "pat_continuing": ("ProfitLossAfterTax",),
    "pat": ("ProfitLossAfterTax",),
    "eps_basic": (
        "BasicAndDilutedEPSAfterExtraordinaryItemsNetOfTaxExpenseForThePeriodNotToBeAnnualized",
    ),
    # "Assets" in these filings is not total assets (ICICI Lombard: a tenth of investments), and
    # the balance sheet is sources = application of funds: no V4 until it is mapped.
    "total_assets": (),
    "equity_and_liabilities": (),
    "total_equity": (),
    "total_liabilities": (),
}

# Life insurers: IRDAI's life format (NSE files it as INTEGRATED_FILING_LI_). Policyholders'
# account: net premium + investment income + other income + transfer from the shareholders'
# account = total income; less benefits, actuarial liability, commission and expenses = surplus.
# PBT comes from the shareholders' account (its income - its expenses). Seen on Canara HSBC Life,
# five quarters to September 2026, all of which tie out exactly. Net premium is the top line, as
# in the IRDAI format; APE and VNB, which analysts track, are not in the XBRL. The ratios
# (solvency, persistency, expenses of management) are tagged as fractions: 1.8041 = 180.41%.
LIFE_INSURANCE: dict[str, tuple[str, ...]] = {
    "revenue": ("NetPremiumIncome",),
    "gross_premium": ("GrossPremiumIncome",),
    "investment_income": ("IncomeFromInvestmentsNet",),
    "other_income": ("PolicyholdersAccountOtherIncome",),
    "transfer_from_shareholders": ("TransferOfFundsFromShareholdersAccount",),
    "total_income": ("Income",),
    "total_expenses": ("Expenses",),
    "surplus": ("SurplusShownInTheRevenueAccount",),
    "shareholders_income": ("ShareholdersAccountIncome",),
    "shareholders_expenses": ("ShareholdersAccountExpenses",),
    "interest_income": (),  # not lenders: no interest ratios
    "interest_expense": (),
    "exceptional_items": (),
    "extraordinary_items": (),
    "pbt": ("ProfitLossBeforeTax",),
    "tax": ("ProvisionsForTaxes",),
    "pat_continuing": ("ProfitLossAfterTaxBeforeExtraordinaryItems",),
    "pat": ("ProfitLossAfterTaxAndExtraordinaryItems",),
    "eps_basic": (
        "BasicAndDilutedEPSAfterExtraordinaryItemsNetOfTaxExpenseForThePeriodNotToBeAnnualized",
    ),
    "solvency_ratio": ("SolvencyRatio",),
    "persistency_13m": ("PersistencyRatio13ThMonth",),
    "persistency_61m": ("PersistencyRatio61ThMonth",),
    "expense_ratio": ("ExpensesOfManagementRatio",),  # (commission + opex) / gross premium
    # Balance sheet in the sources / application of funds layout: not mapped, so no V4.
    "total_assets": (),
    "equity_and_liabilities": (),
    "total_equity": (),
    "total_liabilities": (),
}

# Lenders' interest ratios (interest.py): NIM, yield, cost of borrowing, spread. Interest income
# and expense are the "interest_income" / "interest_expense" lines in each format's table above.
# Balance-sheet lines summed into interest-earning assets and interest-bearing funding, whichever a
# filing tags (banks: RBI Schedule 3 names; NBFCs: Division III names). Cash and balances with the
# RBI (mostly cash in hand and the CRR, which earns nothing) and cash equivalents are left out; so
# is DebtSecurities on the asset side, which in Division III is a liability (debt issued). Seen on
# HDFC Bank and Bajaj Finance, 30 September 2026; banks file the balance sheet half-yearly only.
EARNING_ASSETS = (
    "Advances",  # banks
    "Loans",  # NBFCs
    "Investments",
    "BalancesWithBanksAndMoneyAtCallAndShortNotice",  # banks
    "BankBalanceOtherThanCashAndCashEquivalents",  # NBFCs
)
FUNDING = ("Deposits", "Borrowings", "DebtSecurities", "SubordinatedLiabilities")

BY_TAXONOMY = {
    "indas": INDAS,
    "banking": BANKING,
    "nbfc": NBFC,
    "insurance": INSURANCE,
    "life_insurance": LIFE_INSURANCE,
}

# Non-numeric facts that describe the filing itself. All seen in the 2026-10-13 spike.
META_ELEMENTS = {
    "symbol": "Symbol",
    "scrip_code": "ScripCode",
    "company_name": "NameOfTheCompany",
    "fy_start": "DateOfStartOfFinancialYear",
    "fy_end": "DateOfEndOfFinancialYear",
    "period_start": "DateOfStartOfReportingPeriod",
    "period_end": "DateOfEndOfReportingPeriod",
    "nature": "NatureOfReportStandaloneConsolidated",
    "audited": "WhetherResultsAreAuditedOrUnaudited",
}


def candidates(logical: str, taxonomy: str = "indas") -> tuple[str, ...]:
    """Element names for a logical name. A taxonomy's own entry wins, even when empty (the item
    does not exist in that format); names it doesn't list fall back to Ind-AS."""
    table = BY_TAXONOMY.get(taxonomy) or INDAS
    if logical in table:
        return table[logical]
    return INDAS.get(logical, ())


def detect_taxonomy(elements: set[str]) -> str | None:
    """Results format from the elements a filing tags, or None when nothing marks it.

    Integrated filings share one schema for every filer, so the schema name no longer tells banks
    and insurers apart. Banks and insurers never tag RevenueFromOperations; NBFCs do, and also tag
    InterestEarned as part of their revenue, so that alone is not a bank marker.
    """
    if "RevenueFromOperations" in elements:
        return None
    if {"InterestEarned", "InterestExpended"} <= elements:
        return "banking"
    # Life names: general insurers write premium (GrossPremiumsWritten), life insurers receive it.
    if elements & {"GrossPremiumIncome", "NetPremiumIncome", "PersistencyRatio13ThMonth"}:
        return "life_insurance"
    if elements & {"PremiumEarned", "GrossPremiumsWritten", "NetPremiumWritten"}:
        return "insurance"
    return None
