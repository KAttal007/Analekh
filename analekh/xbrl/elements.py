"""Fixed XBRL vocabulary for results filings (design doc 8.1).

Element names follow the BSE Ind-AS results taxonomy (prefix ``in-bse-fin``); integrated filings
(``in-capmkt``, since March 2025) use the same names. Banks and insurers file in their regulators'
formats (RBI, IRDAI) with different element sets, each in its own table here. NBFCs file the
Ind-AS layout (Schedule III Division III) and use the Ind-AS names (seen on Bajaj Finance).

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
    "exceptional_items": ("ExceptionalItemsBeforeTax",),
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
}
NBFC: dict[str, tuple[str, ...]] = {}  # Ind-AS names apply

# General insurers: IRDAI format. Revenue account: premium earned + investment income + other
# income = operating income; less operating expenses (claims, commission, expenses) = operating
# profit, which moves to the shareholders' account; plus shareholders' investment and other
# income, less non-operating expenses = PBT. Seen on ICICI Lombard (June 2026), which ties out.
# Life insurers file a different revenue account: not yet seen (verify when one is ingested).
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
    "exceptional_items": (),
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

BY_TAXONOMY = {"indas": INDAS, "banking": BANKING, "nbfc": NBFC, "insurance": INSURANCE}

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
    if elements & {"PremiumEarned", "GrossPremiumsWritten", "NetPremiumWritten"}:
        return "insurance"
    return None
