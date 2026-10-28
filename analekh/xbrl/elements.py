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

INDAS: dict[str, tuple[str, ...]] = {
    "revenue": ("RevenueFromOperations",),
    "other_income": ("OtherIncome",),
    "total_income": ("Income", "TotalIncome"),  # verify TotalIncome (Income seen)
    "total_expenses": ("Expenses", "TotalExpenses"),  # verify TotalExpenses (Expenses seen)
    "finance_costs": ("FinanceCosts",),
    "depreciation": ("DepreciationDepletionAndAmortisationExpense",),
    "exceptional_items": ("ExceptionalItemsBeforeTax", "ExceptionalItems"),
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
    "interest_income": ("InterestEarned",),
    "interest_expense": ("FinanceCosts",),
    "impairment": ("ImpairmentOnFinancialInstruments",),
}

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
    "transfer_to_reserves": ("TransferToReserves",),
    "interest_income": (),  # not lenders: no interest ratios
    "interest_expense": (),
    "exceptional_items": (),
    "extraordinary_items": (),
    "pbt": ("ProfitOrLossBeforeTax",),
    "tax": ("ProvisionForTax",),
    "pat_continuing": ("ProfitLossAfterTax",),
    "pat": ("ProfitLossAfterTax",),
    "eps_basic": ("BasicAndDilutedEPSAfterExtraordinaryItemsNetOfTaxExpenseForThePeriodNotToBeAnnualized",),
    # the balance sheet is sources = application of funds: no V4 until it is mapped.
    "total_assets": (),
    "equity_and_liabilities": (),
    "total_equity": (),
    "total_liabilities": (),
}

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
    "eps_basic": ("BasicAndDilutedEPSAfterExtraordinaryItemsNetOfTaxExpenseForThePeriodNotToBeAnnualized",),
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
    """Results format from elements a filing tags, or None when nothing marks it.

    Integrated filings share one schema for every filer, so schema name no longer separates banks
    and insurers. Banks and insurers never tag RevenueFromOperations; NBFCs do, and also tag
    InterestEarned as part of revenue, so that alone isn't a bank marker.
    """
    if "RevenueFromOperations" in elements:
        return None
    if {"InterestEarned", "InterestExpended"} <= elements:
        return "banking"
    if elements & {"GrossPremiumIncome", "NetPremiumIncome", "PersistencyRatio13ThMonth"}:
        return "life_insurance"
    if elements & {"PremiumEarned", "GrossPremiumsWritten", "NetPremiumWritten"}:
        return "insurance"
    return None
