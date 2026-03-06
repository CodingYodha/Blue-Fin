import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Any
import pandas as pd
import numpy as np
import os

from .model_loader import MLArtifacts, get_sector_config
from .data_reader import read_go_features

logger = logging.getLogger(__name__)

@dataclass
class FeatureAssemblyResult:
    X1: pd.DataFrame          # M1 features — all columns including intermediates
    X2: pd.DataFrame          # M2 features
    X3: pd.DataFrame          # M3 features
    X4: pd.DataFrame          # M4 features
    sector: str
    sector_config: dict
    revenue_crore: float
    net_worth_crore: float
    assembly_warnings: List[str]
    raw_features: dict        # UNSCALED raw values — for Layer 1 + SHAP human labels

def encode_safe(encoder, value: str) -> int:
    try:
        return int(encoder.transform([value])[0])
    except (ValueError, KeyError, Exception):
        logger.warning(f"Unseen label '{value}' for encoder — using 0")
        return 0

def safe_float(d: dict, *keys, default=0.0) -> float:
    """Nested .get() with safe numeric cast and null logging."""
    val = d
    for k in keys:
        val = val.get(k) if isinstance(val, dict) else None
        if val is None:
            logger.warning(f"Missing field: {'.'.join(str(k) for k in keys)}")
            return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

async def assemble_features(job_id: str, artifacts: MLArtifacts) -> FeatureAssemblyResult:
    warnings_list = []
    
    base_path = f"/tmp/intelli-credit/{job_id}"
    
    def load_json(name):
        try:
            with open(f"{base_path}/{name}", "r") as f:
                return json.load(f)
        except Exception as e:
            msg = f"Failed to load {name}: {e}"
            logger.error(msg)
            warnings_list.append(msg)
            return {}

    rag = load_json("rag_extraction.json")
    ent = load_json("entity_fraud_flags.json")
    res = load_json("research_agent_summary.json")
    ocr = load_json("ocr_output.json")
    
    # Read Go Databricks / DuckDB features using the data_reader module
    try:
        go = await read_go_features(job_id)
    except Exception as e:
        msg = f"Failed to load go_features: {e}"
        logger.error(msg)
        warnings_list.append(msg)
        from .data_reader import GoFeatures
        go = GoFeatures()

    # === BASE VALUES EXTRACTION ===

    # M1 Financial Base
    # rag["financial_summary"]["revenue"]["fy_current"]["value"]
    fin = rag.get("financial_summary", {})
    Revenue_Crore = safe_float(fin, "revenue", "fy_current", "value")
    rev_previous = safe_float(fin, "revenue", "fy_previous", "value")
    ebitda_raw = safe_float(fin, "ebitda", "fy_current", "value")
    pat_raw = safe_float(fin, "pat", "fy_current", "value")
    total_debt = safe_float(fin, "total_debt", "value")
    net_worth = safe_float(fin, "net_worth", "value")
    current_assets = safe_float(fin, "current_assets", "value")
    current_liabilities = safe_float(fin, "current_liabilities", "value")
    interest_expense = safe_float(fin, "interest_expense", "value")
    ebit_raw = safe_float(fin, "ebit", "value")
    operating_cf = safe_float(fin, "operating_cash_flow", "value")
    debt_service = safe_float(fin, "debt_service", "value")
    
    Credit_Rating = safe_float(rag, "rating_intelligence", "current_rating", default="NR")
    if not isinstance(Credit_Rating, str): Credit_Rating = str(Credit_Rating)
    
    Sector = ocr.get("entity_extraction", {}).get("industry", "DEFAULT")

    # M1 Derived Base
    Revenue_Growth_YoY = (Revenue_Crore - rev_previous) / max(abs(rev_previous), 0.001)
    EBITDA_Margin = ebitda_raw / max(Revenue_Crore, 0.001)
    Net_Profit_Margin = pat_raw / max(Revenue_Crore, 0.001)
    Debt_to_Equity = total_debt / max(net_worth, 0.001)
    Interest_Coverage_Ratio = ebit_raw / max(interest_expense, 0.001)
    Current_Ratio = current_assets / max(current_liabilities, 0.001)
    DSCR = operating_cf / max(debt_service, 0.001)
    Cash_Flow_Stability_Index = 0.5
    Revenue_Log = float(np.log1p(Revenue_Crore))
    Rating_Score = {"AAA":40,"AA":37,"A":33,"BBB":28,"BB":20,"B":12,"C":5,"D":0,"NR":18}.get(Credit_Rating, 18)
    
    sector_config = get_sector_config(Sector, artifacts)
    
    DSCR_vs_Sector_Threshold = DSCR - sector_config.get("dscr_ok", 0.0)
    DE_vs_Sector_Max = Debt_to_Equity - sector_config.get("de_max", 0.0)
    EBITDA_vs_Floor = EBITDA_Margin - sector_config.get("ebitda_floor", 0.0)
    Sector_Encoded = encode_safe(artifacts.encoder_sector, Sector)

    # M2 Behaviour Base
    GST_Filing_Delay_Days = float(go.get("gst_filing_delay_days", 0))
    GST_vs_Bank_Variance_Pct = float(go.get("gst_vs_bank_variance_pct", 0.0))
    GSTR_2A_3B_ITC_Mismatch_Pct = float(go.get("gstr_2a_3b_itc_mismatch_pct", 0.0))
    Historical_Defaults = float(go.get("historical_defaults", 0))
    Rating_Downgrades_Count = float(go.get("rating_downgrades_count", 0))
    Payment_Delays_Days = float(go.get("payment_delays_days", 0))
    Tax_Compliance_Score = float(go.get("tax_compliance_score", 0))
    Round_Trip_Transaction_Count = float(go.get("round_trip_transaction_count", 0))
    Cash_Deposit_Ratio = float(go.get("cash_deposit_ratio", 0.0))
    GST_Scrutiny_Notice_Flag = int(go.get("gst_scrutiny_notice_flag", 0))
    GST_Variance_vs_Sector = GST_vs_Bank_Variance_Pct - sector_config.get("gst_var_normal", 0.0)

    # M3 Industry Base
    Industry_Growth_Rate = float(go.get("industry_growth_rate", 0.0))
    Sector_Volatility_Beta = float(go.get("sector_volatility_beta", 0.0))
    Regulatory_Pressure = str(go.get("regulatory_pressure", "Medium"))
    pressure_map = {"Low":1,"Medium":2,"High":3,"Severe":4,"Critical":5}
    numeric_pressure = pressure_map.get(Regulatory_Pressure, 2)
    Commodity_Exposure_Index = float(go.get("commodity_exposure_index", 0.0))
    Supply_Chain_Risk_Score = float(go.get("supply_chain_risk_score", 0.0))
    Sector_News_Sentiment = float(res.get("sector_sentiment_score", 0.0))
    Regulatory_Action_Flag = int(go.get("regulatory_action_flag", 0))

    # M4 Text Base
    Related_Party_Anomaly_Flag = int(ent.get("related_party_anomaly_flag", 0))
    DIN_Disqualification_Flag = int(ent.get("din_disqualification_flag", 0))
    Governance_Issues_Flag = int(ent.get("governance_issues_flag", 0))
    SARFAESI_Action_Flag = int(ent.get("sarfaesi_action_flag", 0))
    
    qual = rag.get("qualitative_signals", {})
    Auditor_Qualified_Opinion_Flag = int(qual.get("auditor_qualification", {}).get("has_qualification", 0))
    Litigation_Count = len(qual.get("litigation_disclosures", []))
    NCLT_Active_Flag = int(res.get("litigation_risk") == "ACTIVE")
    Promoter_Disputes_Flag = int(res.get("promoter_risk") == "HIGH")
    Negative_News_Sentiment = float(res.get("sector_sentiment_score", 0.0))
    
    key_findings = res.get("key_findings", [])
    fraud_keywords = ["ED", "CBI", "SFIO", "FRAUD", "ENFORCEMENT", "LAUNDERING"]
    Fraud_Keywords_Count = len([
        f for f in key_findings
        if any(kw in f.get("finding", "").upper() for kw in fraud_keywords)
    ])

    # === CATEGORY A: Hardcoded threshold flags ===

    # M1 Flags
    NPM_Negative = int(Net_Profit_Margin < 0)
    Liquidity_Stress = int(Current_Ratio < 1.5)
    DSCR_Below_1_2x = int(DSCR < 1.2)
    Profit_Margin_Low = int(Net_Profit_Margin < 0.05)
    EBITDA_Margin_Low = int(EBITDA_Margin < 0.10)
    Revenue_Negative_Growth = int(Revenue_Growth_YoY < 0)
    Revenue_High_Growth = int(Revenue_Growth_YoY > 0.30)
    Liquidity_Risk_Score = max(0.0, 1.5 - Current_Ratio)
    Interest_Burden_Ratio = 1.0 / (Interest_Coverage_Ratio + 0.001)
    DSCR_Stress_Margin = max(0.0, DSCR - 1.0)
    Debt_to_EBITDA = Debt_to_Equity / (EBITDA_Margin + 0.001)
    Credit_Rating_Level = {"AAA":8,"AA":7,"A":6,"BBB":5,"BB":4,"B":3,"C":2,"D":1,"NR":3}.get(Credit_Rating, 3)
    Below_Investment_Grade = int(Credit_Rating_Level < 5)

    # M2 Flags
    GST_Variance_Anomaly = int(GST_vs_Bank_Variance_Pct > 0.20)
    GST_Variance_Severe = int(GST_vs_Bank_Variance_Pct > 0.40)
    GST_Filing_Chronic_Delay = int(GST_Filing_Delay_Days > 30)
    GST_Filing_Severe_Delay = int(GST_Filing_Delay_Days > 60)
    GST_Filing_Risk_Score = min(GST_Filing_Delay_Days / 90.0, 1.0)
    ITC_Mismatch_Fraud_Flag = int(GSTR_2A_3B_ITC_Mismatch_Pct > 0.15)
    ITC_Mismatch_Severe = int(GSTR_2A_3B_ITC_Mismatch_Pct > 0.30)
    Payment_Delay_Chronic = int(Payment_Delays_Days > 30)
    Payment_Delay_Severe = int(Payment_Delays_Days > 90)
    Payment_Delay_Risk = min(Payment_Delays_Days / 180.0, 1.0)
    Round_Trip_Flag = int(Round_Trip_Transaction_Count > 0)
    Round_Trip_Multiple = int(Round_Trip_Transaction_Count > 3)
    Cash_Deposit_High = int(Cash_Deposit_Ratio > 0.40)
    Cash_Deposit_Very_High = int(Cash_Deposit_Ratio > 0.60)
    Previous_Default_Flag = int(Historical_Defaults > 0)
    Previous_Default_Multiple = int(Historical_Defaults > 1)
    Rating_Downgrade_Flag = int(Rating_Downgrades_Count > 0)
    Rating_Downgrade_Multiple = int(Rating_Downgrades_Count > 2)
    Tax_Compliance_Poor = int(Tax_Compliance_Score < 50)
    Tax_Compliance_Fair = int(50 <= Tax_Compliance_Score < 75)

    # M3 Flags
    Industry_Headwind = int(Industry_Growth_Rate < 0.05)
    Industry_Contraction = int(Industry_Growth_Rate < 0)
    Industry_Stagnant = int(0 <= Industry_Growth_Rate < 0.03)
    Sector_High_Volatility = int(Sector_Volatility_Beta > 1.2)
    Sector_Very_High_Volatility = int(Sector_Volatility_Beta > 1.5)
    Sector_Stable = int(Sector_Volatility_Beta < 0.8)
    Supply_Chain_Stressed = int(Supply_Chain_Risk_Score > 60)
    Supply_Chain_Critical = int(Supply_Chain_Risk_Score > 80)
    Commodity_Exposure_High = int(Commodity_Exposure_Index > 0.60)
    Commodity_Exposure_Extreme = int(Commodity_Exposure_Index > 0.80)
    Sector_Sentiment_Headwind = int(Sector_News_Sentiment < -0.40)
    Sector_Sentiment_Neutral = int(-0.40 <= Sector_News_Sentiment <= 0.40)
    Sector_Sentiment_Tailwind = int(Sector_News_Sentiment > 0.40)
    Regulatory_Risk_Amplified = int(Regulatory_Action_Flag == 1 and numeric_pressure > 2)

    # M4 Flags
    Litigation_Chronic = int(Litigation_Count > 2)
    Litigation_Severe = int(Litigation_Count > 5)
    Litigation_Risk_Score = min(Litigation_Count / 10.0, 1.0)
    # NCLT_Critical and SARFAESI_Active already straight from upstream
    NCLT_Critical = int(NCLT_Active_Flag)
    SARFAESI_Active = int(SARFAESI_Action_Flag)
    Distressed_Proceedings = int(NCLT_Active_Flag == 1 or SARFAESI_Action_Flag == 1)
    Fraud_Keywords_Present = int(Fraud_Keywords_Count > 0)
    Fraud_Keywords_Multiple = int(Fraud_Keywords_Count > 2)
    Fraud_Risk_Score = min(Fraud_Keywords_Count / 5.0, 1.0)
    Governance_Critical = int(Governance_Issues_Flag)
    RPT_Anomaly_Flag = int(Related_Party_Anomaly_Flag)
    Promoter_Dispute_Flag = int(Promoter_Disputes_Flag)
    DIN_Disqualified_Flag = int(DIN_Disqualification_Flag)
    Negative_News_Severe = int(Negative_News_Sentiment < -0.60)
    Negative_News_High = int(Negative_News_Sentiment < -0.30)
    Governance_Risk_Score = (Governance_Issues_Flag * 0.25 + Related_Party_Anomaly_Flag * 0.25 + 
                             Promoter_Disputes_Flag * 0.25 + DIN_Disqualification_Flag * 0.25)

    # === CATEGORY C: Population-dependent flags (IMPUTE 0) ===
    Debt_Outlier = 0
    DSCR_Outlier = 0
    Revenue_Decline_Extreme = 0
    GST_Variance_Z_Score = 0
    warn_cat_c = "Population-dependent outlier flags imputed to 0 — single-row inference. Fin_Red_Flag_Count will conservatively undercount."
    logger.warning(warn_cat_c)
    warnings_list.append(warn_cat_c)

    # === CATEGORY B: Composite risk scores ===
    Financial_Risk_Score = (Debt_Outlier * 20 + DSCR_Below_1_2x * 15 + Liquidity_Stress * 15 +
                            Profit_Margin_Low * 10 + Revenue_Negative_Growth * 12 + Below_Investment_Grade * 8) / 100

    Behaviour_Risk_Score = (GST_Variance_Anomaly * 20 + ITC_Mismatch_Fraud_Flag * 20 +
                            Payment_Delay_Chronic * 15 + Round_Trip_Flag * 15 +
                            Cash_Deposit_High * 10 + Previous_Default_Flag * 15 +
                            Rating_Downgrade_Flag * 10 + GST_Scrutiny_Notice_Flag * 20) / 150

    Industry_Risk_Score  = (Industry_Headwind * 15 + Sector_High_Volatility * 15 +
                            Regulatory_Risk_Amplified * 20 + Supply_Chain_Stressed * 15 +
                            Commodity_Exposure_High * 12 + Sector_Sentiment_Headwind * 10) / 100

    Character_Risk_Score = (NCLT_Active_Flag * 25 + SARFAESI_Action_Flag * 20 +
                            Fraud_Keywords_Present * 20 + Governance_Issues_Flag * 15 +
                            Related_Party_Anomaly_Flag * 15 + DIN_Disqualification_Flag * 12 +
                            Auditor_Qualified_Opinion_Flag * 10 + Promoter_Disputes_Flag * 10 +
                            Negative_News_Severe * 8) / 155

    Fin_Red_Flag_Count = Debt_Outlier + DSCR_Outlier + Revenue_Decline_Extreme + NPM_Negative + Liquidity_Stress
    Critical_Financial_Distress = int(Fin_Red_Flag_Count >= 2)

    Beh_Red_Flag_Count = GST_Variance_Anomaly + GST_Filing_Chronic_Delay + ITC_Mismatch_Fraud_Flag + Payment_Delay_Chronic + Round_Trip_Flag
    Critical_Behaviour_Distress = int(Beh_Red_Flag_Count >= 2)

    # === CATEGORY D: Isolation Forest (IMPUTE neutral) ===
    Fin_Is_Anomaly_Flag = 0;  Fin_Anomaly_Score = 0.0
    Beh_Is_Anomaly_Flag = 0;  Beh_Anomaly_Score = 0.0
    Ind_Is_Anomaly_Flag = 0;  Ind_Anomaly_Score = 0.0
    Text_Is_Anomaly_Flag = 0; Text_Anomaly_Score = 0.0
    warn_cat_d = "Isolation Forest anomaly features imputed to neutral (0 / 0.0) — single-row inference."
    logger.warning(warn_cat_d)
    warnings_list.append(warn_cat_d)

    # Create Raw Feature Dictionaries
    raw_m1 = {
        "Revenue_Crore": Revenue_Crore, "Revenue_Growth_YoY": Revenue_Growth_YoY, "EBITDA_Margin": EBITDA_Margin,
        "Net_Profit_Margin": Net_Profit_Margin, "Debt_to_Equity": Debt_to_Equity, "Interest_Coverage_Ratio": Interest_Coverage_Ratio,
        "Current_Ratio": Current_Ratio, "DSCR": DSCR, "Cash_Flow_Stability_Index": Cash_Flow_Stability_Index,
        "Revenue_Log": Revenue_Log, "Rating_Score": Rating_Score, "DSCR_vs_Sector_Threshold": DSCR_vs_Sector_Threshold,
        "DE_vs_Sector_Max": DE_vs_Sector_Max, "EBITDA_vs_Floor": EBITDA_vs_Floor,
        
        "NPM_Negative": NPM_Negative, "Liquidity_Stress": Liquidity_Stress, "DSCR_Below_1_2x": DSCR_Below_1_2x,
        "Profit_Margin_Low": Profit_Margin_Low, "EBITDA_Margin_Low": EBITDA_Margin_Low, "Revenue_Negative_Growth": Revenue_Negative_Growth,
        "Revenue_High_Growth": Revenue_High_Growth, "Liquidity_Risk_Score": Liquidity_Risk_Score, "Interest_Burden_Ratio": Interest_Burden_Ratio,
        "DSCR_Stress_Margin": DSCR_Stress_Margin, "Debt_to_EBITDA": Debt_to_EBITDA, "Credit_Rating_Level": Credit_Rating_Level,
        "Below_Investment_Grade": Below_Investment_Grade,
        
        "Debt_Outlier": Debt_Outlier, "DSCR_Outlier": DSCR_Outlier, "Revenue_Decline_Extreme": Revenue_Decline_Extreme,
        
        "Financial_Risk_Score": Financial_Risk_Score, "Fin_Red_Flag_Count": Fin_Red_Flag_Count, "Critical_Financial_Distress": Critical_Financial_Distress,
        "Fin_Is_Anomaly_Flag": Fin_Is_Anomaly_Flag, "Fin_Anomaly_Score": Fin_Anomaly_Score,
        "Sector_Encoded": Sector_Encoded
    }

    raw_m2 = {
        "GST_Filing_Delay_Days": GST_Filing_Delay_Days, "GST_vs_Bank_Variance_Pct": GST_vs_Bank_Variance_Pct,
        "GSTR_2A_3B_ITC_Mismatch_Pct": GSTR_2A_3B_ITC_Mismatch_Pct, "Historical_Defaults": Historical_Defaults,
        "Rating_Downgrades_Count": Rating_Downgrades_Count, "Payment_Delays_Days": Payment_Delays_Days,
        "Tax_Compliance_Score": Tax_Compliance_Score, "Round_Trip_Transaction_Count": Round_Trip_Transaction_Count,
        "Cash_Deposit_Ratio": Cash_Deposit_Ratio, "GST_Scrutiny_Notice_Flag": GST_Scrutiny_Notice_Flag,
        "GST_Variance_vs_Sector": GST_Variance_vs_Sector,
        
        "GST_Variance_Anomaly": GST_Variance_Anomaly, "GST_Variance_Severe": GST_Variance_Severe,
        "GST_Filing_Chronic_Delay": GST_Filing_Chronic_Delay, "GST_Filing_Severe_Delay": GST_Filing_Severe_Delay,
        "GST_Filing_Risk_Score": GST_Filing_Risk_Score, "ITC_Mismatch_Fraud_Flag": ITC_Mismatch_Fraud_Flag,
        "ITC_Mismatch_Severe": ITC_Mismatch_Severe, "Payment_Delay_Chronic": Payment_Delay_Chronic,
        "Payment_Delay_Severe": Payment_Delay_Severe, "Payment_Delay_Risk": Payment_Delay_Risk,
        "Round_Trip_Flag": Round_Trip_Flag, "Round_Trip_Multiple": Round_Trip_Multiple,
        "Cash_Deposit_High": Cash_Deposit_High, "Cash_Deposit_Very_High": Cash_Deposit_Very_High,
        "Previous_Default_Flag": Previous_Default_Flag, "Previous_Default_Multiple": Previous_Default_Multiple,
        "Rating_Downgrade_Flag": Rating_Downgrade_Flag, "Rating_Downgrade_Multiple": Rating_Downgrade_Multiple,
        "Tax_Compliance_Poor": Tax_Compliance_Poor, "Tax_Compliance_Fair": Tax_Compliance_Fair,
        
        "GST_Variance_Z_Score": GST_Variance_Z_Score,
        
        "Behaviour_Risk_Score": Behaviour_Risk_Score, "Beh_Red_Flag_Count": Beh_Red_Flag_Count,
        "Critical_Behaviour_Distress": Critical_Behaviour_Distress,
        "Beh_Is_Anomaly_Flag": Beh_Is_Anomaly_Flag, "Beh_Anomaly_Score": Beh_Anomaly_Score,
        "Sector_Encoded": Sector_Encoded
    }

    raw_m3 = {
        "Industry_Growth_Rate": Industry_Growth_Rate, "Sector_Volatility_Beta": Sector_Volatility_Beta,
        "Commodity_Exposure_Index": Commodity_Exposure_Index, "Supply_Chain_Risk_Score": Supply_Chain_Risk_Score,
        "Sector_News_Sentiment": Sector_News_Sentiment, "Regulatory_Action_Flag": Regulatory_Action_Flag,
        
        "Industry_Headwind": Industry_Headwind, "Industry_Contraction": Industry_Contraction, "Industry_Stagnant": Industry_Stagnant,
        "Sector_High_Volatility": Sector_High_Volatility, "Sector_Very_High_Volatility": Sector_Very_High_Volatility,
        "Sector_Stable": Sector_Stable, "Supply_Chain_Stressed": Supply_Chain_Stressed, "Supply_Chain_Critical": Supply_Chain_Critical,
        "Commodity_Exposure_High": Commodity_Exposure_High, "Commodity_Exposure_Extreme": Commodity_Exposure_Extreme,
        "Sector_Sentiment_Headwind": Sector_Sentiment_Headwind, "Sector_Sentiment_Neutral": Sector_Sentiment_Neutral,
        "Sector_Sentiment_Tailwind": Sector_Sentiment_Tailwind, "Regulatory_Risk_Amplified": Regulatory_Risk_Amplified,
        
        "Industry_Risk_Score": Industry_Risk_Score,
        "Ind_Is_Anomaly_Flag": Ind_Is_Anomaly_Flag, "Ind_Anomaly_Score": Ind_Anomaly_Score,
        "Sector_Encoded": Sector_Encoded, "Revenue_Log": Revenue_Log
    }

    raw_m4 = {
        "Litigation_Count": Litigation_Count, "Fraud_Keywords_Count": Fraud_Keywords_Count,
        "Negative_News_Sentiment": Negative_News_Sentiment, "Related_Party_Anomaly_Flag": Related_Party_Anomaly_Flag,
        "DIN_Disqualification_Flag": DIN_Disqualification_Flag, "Governance_Issues_Flag": Governance_Issues_Flag,
        "SARFAESI_Action_Flag": SARFAESI_Action_Flag, "Auditor_Qualified_Opinion_Flag": Auditor_Qualified_Opinion_Flag,
        "NCLT_Active_Flag": NCLT_Active_Flag, "Promoter_Disputes_Flag": Promoter_Disputes_Flag,
        
        "Litigation_Chronic": Litigation_Chronic, "Litigation_Severe": Litigation_Severe, "Litigation_Risk_Score": Litigation_Risk_Score,
        "NCLT_Critical": NCLT_Critical, "SARFAESI_Active": SARFAESI_Active, "Distressed_Proceedings": Distressed_Proceedings,
        "Fraud_Keywords_Present": Fraud_Keywords_Present, "Fraud_Keywords_Multiple": Fraud_Keywords_Multiple,
        "Fraud_Risk_Score": Fraud_Risk_Score, "Governance_Critical": Governance_Critical,
        "RPT_Anomaly_Flag": RPT_Anomaly_Flag, "Promoter_Dispute_Flag": Promoter_Dispute_Flag,
        "DIN_Disqualified_Flag": DIN_Disqualified_Flag, "Negative_News_Severe": Negative_News_Severe,
        "Negative_News_High": Negative_News_High, "Governance_Risk_Score": Governance_Risk_Score,
        
        "Character_Risk_Score": Character_Risk_Score,
        "Text_Is_Anomaly_Flag": Text_Is_Anomaly_Flag, "Text_Anomaly_Score": Text_Anomaly_Score,
        "Sector_Encoded": Sector_Encoded
    }

    # Prepare complete raw dict
    raw_features_all = {**raw_m1, **raw_m2, **raw_m3, **raw_m4}

    # DataFrames for Scaling
    X1 = pd.DataFrame([raw_m1])
    X2 = pd.DataFrame([raw_m2])
    X3 = pd.DataFrame([raw_m3])
    X4 = pd.DataFrame([raw_m4])

    # === CATEGORY E: SCALING ===
    def scale_df(df, scaler):
        if scaler is None:
            msg = "Scaler not found — passing unscaled features. Scores may drift."
            logger.warning(msg)
            warnings_list.append(msg)
            return df
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        df_scaled = df.copy()
        df_scaled[numeric_cols] = scaler.transform(df[numeric_cols])
        return df_scaled

    X1_scaled = scale_df(X1, artifacts.scaler_financial)
    X2_scaled = scale_df(X2, artifacts.scaler_behaviour)
    X3_scaled = scale_df(X3, artifacts.scaler_industry)
    X4_scaled = scale_df(X4, artifacts.scaler_text)

    return FeatureAssemblyResult(
        X1=X1_scaled,
        X2=X2_scaled,
        X3=X3_scaled,
        X4=X4_scaled,
        sector=Sector,
        sector_config=sector_config,
        revenue_crore=Revenue_Crore,
        net_worth_crore=net_worth,
        assembly_warnings=warnings_list,
        raw_features=raw_features_all
    )
