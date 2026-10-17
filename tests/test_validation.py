from datetime import date
from decimal import Decimal

from analekh.validate.rules import HistoryFact, KpiValue, ValidationContext, validate
from analekh.xbrl.parser import parse_instance
from tests.xbrl_factory import BS, Q2, build_instance, pnl, q2_instance

Q1_HISTORY = [
    HistoryFact(
        "RevenueFromOperations", date(2026, 4, 1), date(2026, 6, 30), Decimal(900_000_000), 1
    ),
    HistoryFact(
        "ProfitLossForPeriod", date(2026, 4, 1), date(2026, 6, 30), Decimal(165_000_000), 1
    ),
]


def by_rule(report):
    return {r.rule: r for r in report.results}


def test_consistent_filing_passes_everything():
    ctx = ValidationContext(
        parse_instance(q2_instance()), filed_at=date(2026, 11, 10), history=Q1_HISTORY
    )
    report = validate(ctx)
    results = by_rule(report)
    for rule in ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9"):
        assert results[rule].status == "pass", results[rule]
    assert results["V10"].status == "skip"
    assert not report.blocks_auto_apply


def test_v1_failure_blocks_auto_apply():
    values = pnl(1_000_000_000, 50_000_000, 800_000_000, 62_500_000)
    values["Income"] += 10_000_000
    report = validate(
        ValidationContext(parse_instance(build_instance(**Q2, values_q=values, values_instant=BS)))
    )
    assert by_rule(report)["V1"].status == "fail"
    assert report.blocks_auto_apply


def test_v4_balance_sheet_mismatch():
    report = validate(
        ValidationContext(
            parse_instance(
                build_instance(
                    **Q2,
                    values_q=pnl(1, 0, 0, 0),
                    values_instant={"Assets": 5_000_000_000, "EquityAndLiabilities": 4_000_000_000},
                )
            )
        )
    )
    assert by_rule(report)["V4"].status == "fail"


def test_untagged_elements_skip_not_fail():
    report = validate(
        ValidationContext(
            parse_instance(build_instance(**Q2, values_q={"RevenueFromOperations": 100}))
        )
    )
    results = by_rule(report)
    assert results["V1"].status == "skip"
    assert results["V4"].status == "skip"
    assert not report.blocks_auto_apply


def test_v5_detects_quarter_not_matching_ytd():
    history = [
        HistoryFact(
            "RevenueFromOperations", date(2026, 4, 1), date(2026, 6, 30), Decimal(800_000_000), 1
        )
    ]
    result = by_rule(validate(ValidationContext(parse_instance(q2_instance()), history=history)))[
        "V5"
    ]
    assert result.status == "fail"


def test_v6_declared_period_wins():
    ctx = ValidationContext(parse_instance(q2_instance(declared_end=date(2026, 9, 29))))
    assert by_rule(validate(ctx))["V6"].status == "fail"
    assert ctx.period_end == date(2026, 9, 29)


def test_v7_swing_highlighted():
    history = [
        HistoryFact(
            "RevenueFromOperations", date(2026, 4, 1), date(2026, 6, 30), Decimal(500_000_000), 1
        )
    ]
    result = by_rule(validate(ValidationContext(parse_instance(q2_instance()), history=history)))[
        "V7"
    ]
    assert result.status == "fail" and result.action == "highlight"


def test_v8_late_filing():
    ctx = ValidationContext(parse_instance(q2_instance()), filed_at=date(2027, 4, 15))
    assert by_rule(validate(ctx))["V8"].status == "fail"


def v8(instance: bytes, filed_at: date):
    return by_rule(validate(ValidationContext(parse_instance(instance), filed_at=filed_at)))["V8"]


def test_v8_quarter_deadline_is_45_days():
    # Quarter ended 30 September: day 45 is 14 November; XBRL may follow the PDF a day later.
    assert v8(q2_instance(), date(2026, 11, 14)).details == {"lag_days": 45, "deadline_days": 45}
    assert v8(q2_instance(), date(2026, 11, 15)).status == "pass"
    late = v8(q2_instance(), date(2026, 11, 16))
    assert late.status == "fail" and late.action == "label"


def test_v8_year_end_deadline_is_60_days():
    q4 = build_instance(
        q_start=date(2027, 1, 1),
        q_end=date(2027, 3, 31),
        ytd_start=date(2026, 4, 1),
        values_q=pnl(1_000_000_000, 50_000_000, 800_000_000, 62_500_000),
        values_ytd=pnl(4_000_000_000, 200_000_000, 3_200_000_000, 250_000_000),
        values_instant=BS,
    )
    assert v8(q4, date(2027, 5, 30)).details == {"lag_days": 60, "deadline_days": 60}
    assert v8(q4, date(2027, 5, 30)).status == "pass"
    assert v8(q4, date(2027, 6, 1)).status == "fail"


def test_v9_restatement_diff():
    history = [
        HistoryFact(
            "RevenueFromOperations", date(2026, 7, 1), date(2026, 9, 30), Decimal(990_000_000), 7
        )
    ]
    result = by_rule(validate(ValidationContext(parse_instance(q2_instance()), history=history)))[
        "V9"
    ]
    assert result.status == "fail"
    assert result.details["diffs"][0]["old_filing_id"] == 7


def test_v10_ai_value_conflict():
    kpis = [KpiValue("revenue", date(2026, 9, 30), Decimal(1_200_000_000))]
    result = by_rule(validate(ValidationContext(parse_instance(q2_instance()), kpis=kpis)))["V10"]
    assert result.status == "fail"


def test_report_is_json_serialisable():
    import json

    report = validate(ValidationContext(parse_instance(q2_instance()), history=Q1_HISTORY))
    json.dumps(report.as_dict())


def test_v2_adds_exceptional_items_as_tagged():
    # Tata Elxsi, Q3 FY26 (standalone): a labour-code charge tagged as a negative exceptional item.
    q = {
        "RevenueFromOperations": 9_534_743_000,
        "OtherIncome": 460_382_000,
        "Income": 9_995_125_000,
        "Expenses": 7_575_520_000,
        "ExceptionalItemsBeforeTax": -956_888_000,
        "ProfitBeforeTax": 1_462_717_000,
    }
    instance = build_instance(
        q_start=date(2025, 10, 1),
        q_end=date(2025, 12, 31),
        ytd_start=date(2025, 10, 1),
        values_q=q,
    )
    result = by_rule(validate(ValidationContext(parse_instance(instance))))["V2"]
    assert result.status == "pass", result.message


def _quarter(values: dict[str, int], instant: dict[str, int] | None = None) -> bytes:
    return build_instance(
        q_start=date(2026, 1, 1),
        q_end=date(2026, 3, 31),
        ytd_start=date(2026, 1, 1),
        values_q=values,
        values_instant=instant,
    )


# HDFC Bank, March 2026 quarter (consolidated), in rupees.
HDFC_BANK = {
    "InterestEarned": 871_825_000_000,
    "InterestExpended": 452_204_400_000,
    "OtherIncome": 297_374_400_000,
    "Income": 1_169_199_400_000,
    "OperatingExpenses": 405_878_200_000,
    "ExpenditureExcludingProvisionsAndContingencies": 858_082_600_000,
    "OperatingProfitBeforeProvisionAndContingencies": 311_116_800_000,
    "ProvisionsOtherThanTaxAndContingencies": 34_400_500_000,
    "ExceptionalItems": -7_234_600_000,
    "ProfitLossFromOrdinaryActivitiesBeforeTax": 269_481_700_000,
    "TaxExpense": 65_974_100_000,
    "ProfitLossFromOrdinaryActivitiesAfterTax": 203_507_600_000,
    "ProfitLossForThePeriod": 203_507_600_000,
}
HDFC_BANK_BS = {"Assets": 49_080_408_400_000, "CapitalAndLiabilities": 49_080_408_400_000}

# ICICI Lombard, June 2026 quarter (standalone), general insurer.
ICICI_LOMBARD = {
    "GrossPremiumsWritten": 88_602_700_000,
    "PremiumEarned": 59_500_400_000,
    "IncomeFromInvestmentsNet": 8_578_700_000,
    "OtherIncome": 58_000_000,
    "OperatingIncome": 68_137_100_000,
    "OperatingExpenses": 65_799_200_000,
    "OperatingProfitOrLoss": 2_337_900_000,
    "ShareholdersAccountIncomeFromInvestments": 2_803_100_000,
    "ShareholdersAccountOtherIncome": 78_000_000,
    "NonOperatingExpense": -138_000_000,
    "ProfitOrLossBeforeTax": 5_357_000_000,
    "ProvisionForTax": 1_325_300_000,
    "ProfitLossAfterTax": 4_031_700_000,
}


# Canara HSBC Life, September 2026 quarter (standalone), life insurer. Policyholders' account:
# net premium + investment income + other income + transfer from shareholders = income; income -
# expenses = surplus. Shareholders' account: income - expenses = PBT.
CANARA_HSBC_LIFE = {
    "GrossPremiumIncome": 25_812_500_000,
    "NetPremiumIncome": 25_531_600_000,
    "IncomeFromInvestmentsNet": -334_200_000,
    "PolicyholdersAccountOtherIncome": 64_000_000,
    "TransferOfFundsFromShareholdersAccount": -151_400_000,
    "Income": 25_110_000_000,
    "Expenses": 25_224_900_000,
    "SurplusShownInTheRevenueAccount": -114_900_000,
    "ShareholdersAccountIncome": 378_000_000,
    "ShareholdersAccountExpenses": -104_100_000,
    "ProfitLossBeforeTax": 482_100_000,
    "ProvisionsForTaxes": 51_600_000,
    "ProfitLossAfterTaxBeforeExtraordinaryItems": 430_500_000,
    "ProfitLossAfterTaxAndExtraordinaryItems": 430_500_000,
}


def test_detects_banks_and_insurers_from_their_line_items():
    from analekh.xbrl.elements import detect_taxonomy

    assert parse_instance(_quarter(HDFC_BANK)).taxonomy() == "banking"
    assert parse_instance(_quarter(ICICI_LOMBARD)).taxonomy() == "insurance"
    assert parse_instance(_quarter(CANARA_HSBC_LIFE)).taxonomy() == "life_insurance"
    # NBFCs tag InterestEarned inside their revenue (Bajaj Finance): still Ind-AS.
    assert detect_taxonomy({"RevenueFromOperations", "InterestEarned", "InterestExpended"}) is None


def test_bank_identities_include_provisions():
    ctx = ValidationContext(parse_instance(_quarter(HDFC_BANK, HDFC_BANK_BS)), "banking")
    results = by_rule(validate(ctx))
    for rule in ("V1", "V2", "V3", "V4"):
        assert results[rule].status == "pass", (rule, results[rule].message)
    assert "provisions" in results["V2"].message


def test_insurer_identities_run_through_the_shareholders_account():
    ctx = ValidationContext(parse_instance(_quarter(ICICI_LOMBARD)), "insurance")
    results = by_rule(validate(ctx))
    for rule in ("V1", "V2", "V3"):
        assert results[rule].status == "pass", (rule, results[rule].message)
    assert results["V4"].status == "skip"  # IRDAI balance sheet not mapped yet


def test_reinsurer_transfer_to_reserves_is_deducted_before_pbt():
    # GIC Re, June 2026 quarter (standalone): without the transfer, V2 was off by Rs 160.57 crore.
    gic = {
        **ICICI_LOMBARD,
        "ProfitOrLossBeforeTax": ICICI_LOMBARD["ProfitOrLossBeforeTax"] - 1_605_700_000,
        "TransferToReserves": 1_605_700_000,
    }
    v2 = by_rule(validate(ValidationContext(parse_instance(_quarter(gic)), "insurance")))["V2"]
    assert v2.status == "pass" and "transfer to reserves" in v2.message


def test_life_insurer_identities_run_through_both_accounts():
    ctx = ValidationContext(parse_instance(_quarter(CANARA_HSBC_LIFE)), "life_insurance")
    results = by_rule(validate(ctx))
    for rule in ("V1", "V2", "V3"):
        assert results[rule].status == "pass", (rule, results[rule].message)
    assert "transfer from shareholders" in results["V1"].message
    # Policyholders' income - expenses is the surplus (-11.49 crore), not PBT (48.21 crore).
    assert "Shareholders' account" in results["V2"].message
    assert results["V4"].status == "skip"  # balance sheet not mapped yet


def test_bank_provisions_left_out_fail_v2():
    missing = {**HDFC_BANK, "ProvisionsOtherThanTaxAndContingencies": 0}
    ctx = ValidationContext(parse_instance(_quarter(missing)), "banking")
    assert by_rule(validate(ctx))["V2"].status == "fail"
