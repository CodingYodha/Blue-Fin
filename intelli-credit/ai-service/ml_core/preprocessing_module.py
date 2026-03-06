# """
# =============================================================================
# PREPROCESSING MODULE FOR DEFAULT DETECTION
# =============================================================================
# This module provides advanced preprocessing techniques to improve default
# detection in credit risk models.

# HOW TO USE:
# -----------
# 1. Import this module in your main training script:
#    from preprocessing_module import preprocess_financial_data, preprocess_behaviour_data, 
#                                      preprocess_industry_data, preprocess_text_data

# 2. Apply to each dataset AFTER loading but BEFORE feature engineering:
   
#    df_fin = pd.read_csv("model_1_financial_data.csv")
#    df_fin = preprocess_financial_data(df_fin)
   
#    df_beh = pd.read_csv("model_2_behaviour_data.csv")
#    df_beh = preprocess_behaviour_data(df_beh)
   
#    df_ind = pd.read_csv("model_3_industry_data.csv")
#    df_ind = preprocess_industry_data(df_ind)
   
#    df_unst = pd.read_csv("model_4_unstructured_data.csv")
#    df_unst = preprocess_text_data(df_unst)

# 3. No changes needed to feature engineering section - it reads preprocessed data

# =============================================================================
# """

# import numpy as np
# import pandas as pd
# from sklearn.preprocessing import RobustScaler, StandardScaler
# from sklearn.ensemble import IsolationForest  # <--- ADD THIS IMPORT
# import warnings
# warnings.filterwarnings('ignore')


# # =============================================================================
# # UTILITY FUNCTIONS
# # =============================================================================

# def create_missing_flags(df, cols=None):
#     """
#     Create binary flags for missing values and impute with median.
#     """
#     if cols is None:
#         cols = df.select_dtypes(include=[np.number]).columns
    
#     for col in cols:
#         if df[col].isnull().sum() > 0:
#             # Flag missing values
#             df[f'{col}_missing'] = df[col].isnull().astype(int)
            
#             # ---------update----
#             # Changed from 95th percentile (which forces a high-risk assumption 
#             # and hurts precision) to median imputation. The model will now 
#             # rely on the _missing flag instead of a skewed numeric value.
#             impute_val = df[col].median()
#             # ------update -----
            
#             df[col].fillna(impute_val, inplace=True)
    
#     return df


# def detect_outliers_iqr(df, col, multiplier=1.5):
#     """
#     Detect outliers using IQR method and return flag.
#     """
#     Q75 = df[col].quantile(0.75)
#     Q25 = df[col].quantile(0.25)
#     IQR = Q75 - Q25
    
#     lower_bound = Q25 - multiplier * IQR
#     upper_bound = Q75 + multiplier * IQR
    
#     return (df[col] < lower_bound) | (df[col] > upper_bound)


# def scale_numeric_features(df, cols=None, method='robust'):
#     """
#     Scale numeric features using RobustScaler (preferred for imbalanced data).
#     """
#     if cols is None:
#         cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
#     # ---------update----
#     # FIX: Explicitly remove the target label and ID from the scaling list 
#     # so they remain pristine integers/strings and don't break the training pipeline.
#     cols = [c for c in cols if c not in ['Default_Flag', 'Company_ID']]
#     # ------update -----
    
#     if method == 'robust':
#         scaler = RobustScaler()
#     else:
#         scaler = StandardScaler()
    
#     df[cols] = scaler.fit_transform(df[cols])
#     return df

# def apply_anomaly_detection(df, cols, prefix):
#     """
#     Uses Isolation Forest to detect minority-class profiles (defaults) 
#     without requiring the target label. Returns a continuous score AND a hard binary flag.
#     """
#     temp_df = df[cols].copy()
#     temp_df.fillna(temp_df.median(), inplace=True)
    
#     # Configure for a roughly 5% anomaly rate (matches your 4.7% default rate)
#     iso = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    
#     # ---------update----
#     # Add a HARD binary flag (1 = Anomaly, 0 = Normal) for instant tree-splitting
#     df[f'{prefix}_Is_Anomaly_Flag'] = (iso.fit_predict(temp_df) == -1).astype(int)
#     # ------update -----
    
#     # Keep the continuous score as well (higher score = higher risk)
#     df[f'{prefix}_Anomaly_Score'] = iso.decision_function(temp_df) * -1
    
#     return df

# # =============================================================================
# # MODEL 1: FINANCIAL DATA PREPROCESSING
# # =============================================================================

# def preprocess_financial_data(df_fin):
#     df = df_fin.copy()
#     print("\n  [M1 PREPROCESSING] Starting financial data preprocessing...")
    
#     financial_cols = ['Revenue_Crore', 'EBITDA_Margin', 'Net_Profit_Margin',
#                       'Debt_to_Equity', 'Interest_Coverage_Ratio', 'Current_Ratio',
#                       'DSCR', 'Cash_Flow_Stability_Index', 'Revenue_Growth_YoY']
    
#     df = create_missing_flags(df, financial_cols)
#     print(f"    ✅ Missing value flags created for {len(financial_cols)} columns")
    
#     df['Debt_Outlier'] = detect_outliers_iqr(df, 'Debt_to_Equity', multiplier=3.0).astype(int)
#     df['DSCR_Outlier'] = (df['DSCR'] < df['DSCR'].quantile(0.10)).astype(int)
#     df['Revenue_Decline_Extreme'] = (df['Revenue_Growth_YoY'] < df['Revenue_Growth_YoY'].quantile(0.05)).astype(int)
#     df['NPM_Negative'] = (df['Net_Profit_Margin'] < 0).astype(int)
    
#     df['Debt_to_EBITDA'] = df['Debt_to_Equity'] / (df['EBITDA_Margin'] + 0.001)
#     df['Debt_to_EBITDA'] = df['Debt_to_EBITDA'].clip(upper=df['Debt_to_EBITDA'].quantile(0.95))
#     df['Interest_Burden_Ratio'] = 1.0 / (df['Interest_Coverage_Ratio'] + 0.001)
#     df['DSCR_Stress_Margin'] = (df['DSCR'] - 1.0).clip(lower=0)
#     df['DSCR_Below_1_2x'] = (df['DSCR'] < 1.2).astype(int)
#     df['Liquidity_Stress'] = (df['Current_Ratio'] < 1.5).astype(int)
#     df['Liquidity_Risk_Score'] = (1.5 - df['Current_Ratio']).clip(lower=0)
#     df['Profit_Margin_Low'] = (df['Net_Profit_Margin'] < 0.05).astype(int)
#     df['EBITDA_Margin_Low'] = (df['EBITDA_Margin'] < 0.10).astype(int)
#     df['Revenue_Negative_Growth'] = (df['Revenue_Growth_YoY'] < 0).astype(int)
#     df['Revenue_High_Growth'] = (df['Revenue_Growth_YoY'] > 0.30).astype(int)
    
#     rating_order = {'AAA': 8, 'AA': 7, 'A': 6, 'BBB': 5, 'BB': 4, 'B': 3, 'C': 2, 'D': 1, 'NR': 3}
#     df['Credit_Rating_Level'] = df['Credit_Rating'].map(rating_order).fillna(3)
#     df['Below_Investment_Grade'] = (df['Credit_Rating_Level'] < 5).astype(int)
    
#     df['Financial_Risk_Score'] = (
#         df['Debt_Outlier'] * 20 +
#         df['DSCR_Below_1_2x'] * 15 +
#         df['Liquidity_Stress'] * 15 +
#         df['Profit_Margin_Low'] * 10 +
#         df['Revenue_Negative_Growth'] * 12 +
#         df['Below_Investment_Grade'] * 8
#     )
#     df['Financial_Risk_Score'] = df['Financial_Risk_Score'] / 100
    
#     # ---------update----
#     # 1. Inject Unsupervised Anomaly Detection
#     df = apply_anomaly_detection(df, financial_cols, 'Fin')
    
#     # 2. SLEDGEHAMMER FEATURE: Count simultaneous financial red flags
#     df['Fin_Red_Flag_Count'] = df[['Debt_Outlier', 'DSCR_Outlier', 'Revenue_Decline_Extreme', 'NPM_Negative', 'Liquidity_Stress']].sum(axis=1)
    
#     # If a company has 2 or more major red flags, explicitly flag them as Critical
#     df['Critical_Financial_Distress'] = (df['Fin_Red_Flag_Count'] >= 2).astype(int)
#     print(f"    ✅ Sledgehammer cluster flags and Anomaly flags generated")
#     # ------update -----
    
#     numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
#     numeric_cols = [c for c in numeric_cols if c not in ['Default_Flag', 'Company_ID']]
#     df = scale_numeric_features(df, numeric_cols, method='robust')
    
#     print(f"  [M1 PREPROCESSING] Complete!\n")
#     return df

# # =============================================================================
# # MODEL 2: BEHAVIOUR DATA PREPROCESSING
# # =============================================================================

# def preprocess_behaviour_data(df_beh):
#     df = df_beh.copy()
#     print("\n  [M2 PREPROCESSING] Starting behaviour data preprocessing...")
    
#     behaviour_cols = ['GST_Filing_Delay_Days', 'GST_vs_Bank_Variance_Pct',
#                       'GSTR_2A_3B_ITC_Mismatch_Pct', 'Payment_Delays_Days',
#                       'Tax_Compliance_Score', 'Round_Trip_Transaction_Count',
#                       'Cash_Deposit_Ratio', 'Historical_Defaults',
#                       'Rating_Downgrades_Count']
    
#     df = create_missing_flags(df, behaviour_cols)
    
#     gst_median = df['GST_vs_Bank_Variance_Pct'].median()
#     gst_std = df['GST_vs_Bank_Variance_Pct'].std()
    
#     df['GST_Variance_Anomaly'] = (df['GST_vs_Bank_Variance_Pct'] > 0.20).astype(int)
#     df['GST_Variance_Severe'] = (df['GST_vs_Bank_Variance_Pct'] > 0.40).astype(int)
#     df['GST_Variance_Z_Score'] = (df['GST_vs_Bank_Variance_Pct'] - gst_median) / (gst_std + 0.001)
    
#     df['GST_Filing_Chronic_Delay'] = (df['GST_Filing_Delay_Days'] > 30).astype(int)
#     df['GST_Filing_Severe_Delay'] = (df['GST_Filing_Delay_Days'] > 60).astype(int)
#     df['GST_Filing_Risk_Score'] = np.minimum(df['GST_Filing_Delay_Days'] / 90, 1.0)
    
#     df['ITC_Mismatch_Fraud_Flag'] = (df['GSTR_2A_3B_ITC_Mismatch_Pct'] > 0.15).astype(int)
#     df['ITC_Mismatch_Severe'] = (df['GSTR_2A_3B_ITC_Mismatch_Pct'] > 0.30).astype(int)
    
#     df['Payment_Delay_Chronic'] = (df['Payment_Delays_Days'] > 30).astype(int)
#     df['Payment_Delay_Severe'] = (df['Payment_Delays_Days'] > 90).astype(int)
#     df['Payment_Delay_Risk'] = np.minimum(df['Payment_Delays_Days'] / 180, 1.0)
    
#     df['Round_Trip_Flag'] = (df['Round_Trip_Transaction_Count'] > 0).astype(int)
#     df['Round_Trip_Multiple'] = (df['Round_Trip_Transaction_Count'] > 3).astype(int)
    
#     df['Cash_Deposit_High'] = (df['Cash_Deposit_Ratio'] > 0.40).astype(int)
#     df['Cash_Deposit_Very_High'] = (df['Cash_Deposit_Ratio'] > 0.60).astype(int)
    
#     df['Previous_Default_Flag'] = (df['Historical_Defaults'] > 0).astype(int)
#     df['Previous_Default_Multiple'] = (df['Historical_Defaults'] > 1).astype(int)
    
#     df['Rating_Downgrade_Flag'] = (df['Rating_Downgrades_Count'] > 0).astype(int)
#     df['Rating_Downgrade_Multiple'] = (df['Rating_Downgrades_Count'] > 2).astype(int)
    
#     df['Tax_Compliance_Poor'] = (df['Tax_Compliance_Score'] < 50).astype(int)
#     df['Tax_Compliance_Fair'] = ((df['Tax_Compliance_Score'] >= 50) & 
#                                  (df['Tax_Compliance_Score'] < 75)).astype(int)
    
#     df['Behaviour_Risk_Score'] = (
#         df['GST_Variance_Anomaly'] * 20 +
#         df['ITC_Mismatch_Fraud_Flag'] * 20 +
#         df['Payment_Delay_Chronic'] * 15 +
#         df['Round_Trip_Flag'] * 15 +
#         df['Cash_Deposit_High'] * 10 +
#         df['Previous_Default_Flag'] * 15 +
#         df['Rating_Downgrade_Flag'] * 10 +
#         df['GST_Scrutiny_Notice_Flag'] * 20
#     )
#     df['Behaviour_Risk_Score'] = df['Behaviour_Risk_Score'] / 150
    
#     # ---------update----
#     # 1. Inject Unsupervised Anomaly Detection
#     df = apply_anomaly_detection(df, behaviour_cols, 'Beh')
    
#     # 2. SLEDGEHAMMER FEATURE: Count simultaneous behavioural red flags
#     df['Beh_Red_Flag_Count'] = df[['GST_Variance_Anomaly', 'GST_Filing_Chronic_Delay', 'ITC_Mismatch_Fraud_Flag', 'Payment_Delay_Chronic', 'Round_Trip_Flag']].sum(axis=1)
    
#     # If a company triggers 2 or more fraud/delay flags, explicitly flag as Critical
#     df['Critical_Behaviour_Distress'] = (df['Beh_Red_Flag_Count'] >= 2).astype(int)
#     print(f"    ✅ Sledgehammer cluster flags and Anomaly flags generated")
#     # ------update -----
    
#     numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
#     numeric_cols = [c for c in numeric_cols if c not in ['Default_Flag', 'Company_ID']]
#     df = scale_numeric_features(df, numeric_cols, method='robust')
    
#     print(f"  [M2 PREPROCESSING] Complete!\n")
#     return df


# # =============================================================================
# # MODEL 3: INDUSTRY DATA PREPROCESSING
# # =============================================================================

# def preprocess_industry_data(df_ind):
#     df = df_ind.copy()
#     print("\n  [M3 PREPROCESSING] Starting industry data preprocessing...")
    
#     industry_cols = ['Industry_Growth_Rate', 'Sector_Volatility_Beta',
#                      'Commodity_Exposure_Index', 'Supply_Chain_Risk_Score',
#                      'Sector_News_Sentiment']
    
#     df = create_missing_flags(df, industry_cols)
    
#     # Text mapping for regulatory pressure to allow median calculation
#     pressure_map = {'Low': 1, 'Medium': 2, 'High': 3, 'Severe': 4, 'Critical': 5}
#     numeric_pressure = df['Regulatory_Pressure'].map(pressure_map).fillna(2)
    
#     df['Industry_Headwind'] = (df['Industry_Growth_Rate'] < 0.05).astype(int)
#     df['Industry_Contraction'] = (df['Industry_Growth_Rate'] < 0).astype(int)
#     df['Industry_Stagnant'] = ((df['Industry_Growth_Rate'] >= 0) & 
#                                (df['Industry_Growth_Rate'] < 0.03)).astype(int)
    
#     df['Sector_High_Volatility'] = (df['Sector_Volatility_Beta'] > 1.2).astype(int)
#     df['Sector_Very_High_Volatility'] = (df['Sector_Volatility_Beta'] > 1.5).astype(int)
#     df['Sector_Stable'] = (df['Sector_Volatility_Beta'] < 0.8).astype(int)
    
#     df['Regulatory_Risk_Amplified'] = (
#         (df['Regulatory_Action_Flag'] == 1) & 
#         (numeric_pressure > numeric_pressure.median())
#     ).astype(int)
    
#     df['Supply_Chain_Stressed'] = (df['Supply_Chain_Risk_Score'] > 60).astype(int)
#     df['Supply_Chain_Critical'] = (df['Supply_Chain_Risk_Score'] > 80).astype(int)
    
#     df['Commodity_Exposure_High'] = (df['Commodity_Exposure_Index'] > 0.60).astype(int)
#     df['Commodity_Exposure_Extreme'] = (df['Commodity_Exposure_Index'] > 0.80).astype(int)
    
#     df['Sector_Sentiment_Headwind'] = (df['Sector_News_Sentiment'] < -0.40).astype(int)
#     df['Sector_Sentiment_Neutral'] = ((df['Sector_News_Sentiment'] >= -0.40) & 
#                                       (df['Sector_News_Sentiment'] <= 0.40)).astype(int)
#     df['Sector_Sentiment_Tailwind'] = (df['Sector_News_Sentiment'] > 0.40).astype(int)
    
#     df['Industry_Risk_Score'] = (
#         df['Industry_Headwind'] * 15 +
#         df['Sector_High_Volatility'] * 15 +
#         df['Regulatory_Risk_Amplified'] * 20 +
#         df['Supply_Chain_Stressed'] * 15 +
#         df['Commodity_Exposure_High'] * 12 +
#         df['Sector_Sentiment_Headwind'] * 10
#     )
#     df['Industry_Risk_Score'] = df['Industry_Risk_Score'] / 100
    
#     # ---------update----
#     # Inject Isolation Forest for Industry Data
#     df = apply_anomaly_detection(df, industry_cols, 'Ind')
#     print(f"    ✅ Isolation Forest Anomaly Scores generated (Industry)")
#     # ------update -----
    
#     numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
#     numeric_cols = [c for c in numeric_cols if c not in ['Default_Flag', 'Company_ID']]
#     df = scale_numeric_features(df, numeric_cols, method='robust')
#     print(f"  [M3 PREPROCESSING] Complete!\n")
#     return df


# # =============================================================================
# # MODEL 4: UNSTRUCTURED/TEXT DATA PREPROCESSING
# # =============================================================================

# def preprocess_text_data(df_unst):
#     df = df_unst.copy()
#     print("\n  [M4 PREPROCESSING] Starting text/unstructured preprocessing...")
    
#     text_cols = ['Litigation_Count', 'Fraud_Keywords_Count', 'Negative_News_Sentiment',
#                  'NCLT_Active_Flag', 'Promoter_Disputes_Flag', 'Governance_Issues_Flag',
#                  'Related_Party_Anomaly_Flag', 'DIN_Disqualification_Flag',
#                  'Auditor_Qualified_Opinion_Flag', 'SARFAESI_Action_Flag']
    
#     df = create_missing_flags(df, text_cols)
    
#     df['Litigation_Chronic'] = (df['Litigation_Count'] > 2).astype(int)
#     df['Litigation_Severe'] = (df['Litigation_Count'] > 5).astype(int)
#     df['Litigation_Risk_Score'] = np.minimum(df['Litigation_Count'] / 10, 1.0)
    
#     df['NCLT_Critical'] = df['NCLT_Active_Flag'].astype(int)
#     df['SARFAESI_Active'] = df['SARFAESI_Action_Flag'].astype(int)
    
#     df['Distressed_Proceedings'] = (
#         (df['NCLT_Active_Flag'] == 1) | (df['SARFAESI_Action_Flag'] == 1)
#     ).astype(int)
    
#     df['Fraud_Keywords_Present'] = (df['Fraud_Keywords_Count'] > 0).astype(int)
#     df['Fraud_Keywords_Multiple'] = (df['Fraud_Keywords_Count'] > 2).astype(int)
#     df['Fraud_Risk_Score'] = np.minimum(df['Fraud_Keywords_Count'] / 5, 1.0)
    
#     df['Governance_Critical'] = df['Governance_Issues_Flag'].astype(int)
#     df['RPT_Anomaly_Flag'] = df['Related_Party_Anomaly_Flag'].astype(int)
#     df['Promoter_Dispute_Flag'] = df['Promoter_Disputes_Flag'].astype(int)
#     df['DIN_Disqualified_Flag'] = df['DIN_Disqualification_Flag'].astype(int)
    
#     df['Governance_Risk_Score'] = (
#         df['Governance_Issues_Flag'] * 0.25 +
#         df['Related_Party_Anomaly_Flag'] * 0.25 +
#         df['Promoter_Disputes_Flag'] * 0.25 +
#         df['DIN_Disqualification_Flag'] * 0.25
#     )
    
#     df['Auditor_Qualification_Flag'] = df['Auditor_Qualified_Opinion_Flag'].astype(int)
    
#     df['Negative_News_Severe'] = (df['Negative_News_Sentiment'] < -0.60).astype(int)
#     df['Negative_News_High'] = (df['Negative_News_Sentiment'] < -0.30).astype(int)
    
#     df['Character_Risk_Score'] = (
#         df['NCLT_Active_Flag'] * 25 +
#         df['SARFAESI_Action_Flag'] * 20 +
#         df['Fraud_Keywords_Present'] * 20 +
#         df['Governance_Issues_Flag'] * 15 +
#         df['Related_Party_Anomaly_Flag'] * 15 +
#         df['DIN_Disqualification_Flag'] * 12 +
#         df['Auditor_Qualified_Opinion_Flag'] * 10 +
#         df['Promoter_Disputes_Flag'] * 10 +
#         df['Negative_News_Severe'] * 8
#     )
#     df['Character_Risk_Score'] = df['Character_Risk_Score'] / 155
    
#     # ---------update----
#     # Inject Isolation Forest for Text Data
#     df = apply_anomaly_detection(df, text_cols, 'Text')
#     print(f"    ✅ Isolation Forest Anomaly Scores generated (Text)")
#     # ------update -----
    
#     numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
#     numeric_cols = [c for c in numeric_cols if c not in ['Default_Flag', 'Company_ID']]
#     df = scale_numeric_features(df, numeric_cols, method='robust')
#     print(f"  [M4 PREPROCESSING] Complete!\n")
#     return df


# def apply_all_preprocessing(df_fin, df_beh, df_ind, df_unst):
#     df_fin = preprocess_financial_data(df_fin)
#     df_beh = preprocess_behaviour_data(df_beh)
#     df_ind = preprocess_industry_data(df_ind)
#     df_unst = preprocess_text_data(df_unst)
#     return df_fin, df_beh, df_ind, df_unst


"""
=============================================================================
PREPROCESSING MODULE FOR DEFAULT DETECTION
=============================================================================
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.ensemble import IsolationForest
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def apply_anomaly_detection(df, cols, prefix):
    """
    Uses Isolation Forest to detect minority-class profiles (defaults).
    Returns a continuous score AND a hard binary flag.
    """
    temp_df = df[cols].copy()
    temp_df.fillna(temp_df.median(), inplace=True)
    
    iso = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    
    # Hard binary flag (1 = Anomaly, 0 = Normal)
    df[f'{prefix}_Is_Anomaly_Flag'] = (iso.fit_predict(temp_df) == -1).astype(int)
    # Continuous score
    df[f'{prefix}_Anomaly_Score'] = iso.decision_function(temp_df) * -1
    
    return df

def create_missing_flags(df, cols=None):
    if cols is None:
        cols = df.select_dtypes(include=[np.number]).columns
    for col in cols:
        if df[col].isnull().sum() > 0:
            df[f'{col}_missing'] = df[col].isnull().astype(int)
            df[col].fillna(df[col].median(), inplace=True)
    return df

def detect_outliers_iqr(df, col, multiplier=1.5):
    Q75 = df[col].quantile(0.75)
    Q25 = df[col].quantile(0.25)
    IQR = Q75 - Q25
    return (df[col] < (Q25 - multiplier * IQR)) | (df[col] > (Q75 + multiplier * IQR))

def scale_numeric_features(df, cols=None, method='robust'):
    if cols is None:
        cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    cols = [c for c in cols if c not in ['Default_Flag', 'Company_ID']]
    
    scaler = RobustScaler() if method == 'robust' else StandardScaler()
    df[cols] = scaler.fit_transform(df[cols])
    return df

# =============================================================================
# MODEL 1: FINANCIAL DATA PREPROCESSING
# =============================================================================
def preprocess_financial_data(df_fin):
    df = df_fin.copy()
    print("\n  [M1 PREPROCESSING] Starting financial data preprocessing...")
    
    financial_cols = ['Revenue_Crore', 'EBITDA_Margin', 'Net_Profit_Margin',
                      'Debt_to_Equity', 'Interest_Coverage_Ratio', 'Current_Ratio',
                      'DSCR', 'Cash_Flow_Stability_Index', 'Revenue_Growth_YoY']
    
    df = create_missing_flags(df, financial_cols)
    
    df['Debt_Outlier'] = detect_outliers_iqr(df, 'Debt_to_Equity', multiplier=3.0).astype(int)
    df['DSCR_Outlier'] = (df['DSCR'] < df['DSCR'].quantile(0.10)).astype(int)
    df['Revenue_Decline_Extreme'] = (df['Revenue_Growth_YoY'] < df['Revenue_Growth_YoY'].quantile(0.05)).astype(int)
    df['NPM_Negative'] = (df['Net_Profit_Margin'] < 0).astype(int)
    
    df['Debt_to_EBITDA'] = df['Debt_to_Equity'] / (df['EBITDA_Margin'] + 0.001)
    df['Debt_to_EBITDA'] = df['Debt_to_EBITDA'].clip(upper=df['Debt_to_EBITDA'].quantile(0.95))
    df['Interest_Burden_Ratio'] = 1.0 / (df['Interest_Coverage_Ratio'] + 0.001)
    df['DSCR_Stress_Margin'] = (df['DSCR'] - 1.0).clip(lower=0)
    df['DSCR_Below_1_2x'] = (df['DSCR'] < 1.2).astype(int)
    df['Liquidity_Stress'] = (df['Current_Ratio'] < 1.5).astype(int)
    df['Liquidity_Risk_Score'] = (1.5 - df['Current_Ratio']).clip(lower=0)
    df['Profit_Margin_Low'] = (df['Net_Profit_Margin'] < 0.05).astype(int)
    df['EBITDA_Margin_Low'] = (df['EBITDA_Margin'] < 0.10).astype(int)
    df['Revenue_Negative_Growth'] = (df['Revenue_Growth_YoY'] < 0).astype(int)
    df['Revenue_High_Growth'] = (df['Revenue_Growth_YoY'] > 0.30).astype(int)
    
    rating_order = {'AAA': 8, 'AA': 7, 'A': 6, 'BBB': 5, 'BB': 4, 'B': 3, 'C': 2, 'D': 1, 'NR': 3}
    df['Credit_Rating_Level'] = df['Credit_Rating'].map(rating_order).fillna(3)
    df['Below_Investment_Grade'] = (df['Credit_Rating_Level'] < 5).astype(int)
    
    df['Financial_Risk_Score'] = (
        df['Debt_Outlier'] * 20 + df['DSCR_Below_1_2x'] * 15 +
        df['Liquidity_Stress'] * 15 + df['Profit_Margin_Low'] * 10 +
        df['Revenue_Negative_Growth'] * 12 + df['Below_Investment_Grade'] * 8
    ) / 100
    
    df = apply_anomaly_detection(df, financial_cols, 'Fin')
    df['Fin_Red_Flag_Count'] = df[['Debt_Outlier', 'DSCR_Outlier', 'Revenue_Decline_Extreme', 'NPM_Negative', 'Liquidity_Stress']].sum(axis=1)
    df['Critical_Financial_Distress'] = (df['Fin_Red_Flag_Count'] >= 2).astype(int)
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df = scale_numeric_features(df, numeric_cols, method='robust')
    print(f"  [M1 PREPROCESSING] Complete!\n")
    return df

# =============================================================================
# MODEL 2: BEHAVIOUR DATA PREPROCESSING
# =============================================================================
def preprocess_behaviour_data(df_beh):
    df = df_beh.copy()
    print("\n  [M2 PREPROCESSING] Starting behaviour data preprocessing...")
    
    behaviour_cols = ['GST_Filing_Delay_Days', 'GST_vs_Bank_Variance_Pct', 'GSTR_2A_3B_ITC_Mismatch_Pct', 
                      'Payment_Delays_Days', 'Tax_Compliance_Score', 'Round_Trip_Transaction_Count',
                      'Cash_Deposit_Ratio', 'Historical_Defaults', 'Rating_Downgrades_Count']
    
    df = create_missing_flags(df, behaviour_cols)
    
    gst_median = df['GST_vs_Bank_Variance_Pct'].median()
    gst_std = df['GST_vs_Bank_Variance_Pct'].std()
    
    df['GST_Variance_Anomaly'] = (df['GST_vs_Bank_Variance_Pct'] > 0.20).astype(int)
    df['GST_Variance_Severe'] = (df['GST_vs_Bank_Variance_Pct'] > 0.40).astype(int)
    df['GST_Variance_Z_Score'] = (df['GST_vs_Bank_Variance_Pct'] - gst_median) / (gst_std + 0.001)
    
    df['GST_Filing_Chronic_Delay'] = (df['GST_Filing_Delay_Days'] > 30).astype(int)
    df['GST_Filing_Severe_Delay'] = (df['GST_Filing_Delay_Days'] > 60).astype(int)
    df['GST_Filing_Risk_Score'] = np.minimum(df['GST_Filing_Delay_Days'] / 90, 1.0)
    
    df['ITC_Mismatch_Fraud_Flag'] = (df['GSTR_2A_3B_ITC_Mismatch_Pct'] > 0.15).astype(int)
    df['ITC_Mismatch_Severe'] = (df['GSTR_2A_3B_ITC_Mismatch_Pct'] > 0.30).astype(int)
    
    df['Payment_Delay_Chronic'] = (df['Payment_Delays_Days'] > 30).astype(int)
    df['Payment_Delay_Severe'] = (df['Payment_Delays_Days'] > 90).astype(int)
    df['Payment_Delay_Risk'] = np.minimum(df['Payment_Delays_Days'] / 180, 1.0)
    
    df['Round_Trip_Flag'] = (df['Round_Trip_Transaction_Count'] > 0).astype(int)
    df['Round_Trip_Multiple'] = (df['Round_Trip_Transaction_Count'] > 3).astype(int)
    
    df['Cash_Deposit_High'] = (df['Cash_Deposit_Ratio'] > 0.40).astype(int)
    df['Cash_Deposit_Very_High'] = (df['Cash_Deposit_Ratio'] > 0.60).astype(int)
    
    df['Previous_Default_Flag'] = (df['Historical_Defaults'] > 0).astype(int)
    df['Previous_Default_Multiple'] = (df['Historical_Defaults'] > 1).astype(int)
    
    df['Rating_Downgrade_Flag'] = (df['Rating_Downgrades_Count'] > 0).astype(int)
    df['Rating_Downgrade_Multiple'] = (df['Rating_Downgrades_Count'] > 2).astype(int)
    
    df['Tax_Compliance_Poor'] = (df['Tax_Compliance_Score'] < 50).astype(int)
    df['Tax_Compliance_Fair'] = ((df['Tax_Compliance_Score'] >= 50) & (df['Tax_Compliance_Score'] < 75)).astype(int)
    
    df['Behaviour_Risk_Score'] = (
        df['GST_Variance_Anomaly'] * 20 + df['ITC_Mismatch_Fraud_Flag'] * 20 +
        df['Payment_Delay_Chronic'] * 15 + df['Round_Trip_Flag'] * 15 +
        df['Cash_Deposit_High'] * 10 + df['Previous_Default_Flag'] * 15 +
        df['Rating_Downgrade_Flag'] * 10 + df['GST_Scrutiny_Notice_Flag'] * 20
    ) / 150
    
    df = apply_anomaly_detection(df, behaviour_cols, 'Beh')
    df['Beh_Red_Flag_Count'] = df[['GST_Variance_Anomaly', 'GST_Filing_Chronic_Delay', 'ITC_Mismatch_Fraud_Flag', 'Payment_Delay_Chronic', 'Round_Trip_Flag']].sum(axis=1)
    df['Critical_Behaviour_Distress'] = (df['Beh_Red_Flag_Count'] >= 2).astype(int)
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df = scale_numeric_features(df, numeric_cols, method='robust')
    print(f"  [M2 PREPROCESSING] Complete!\n")
    return df

# =============================================================================
# MODEL 3: INDUSTRY DATA PREPROCESSING
# =============================================================================
def preprocess_industry_data(df_ind):
    df = df_ind.copy()
    print("\n  [M3 PREPROCESSING] Starting industry data preprocessing...")
    
    industry_cols = ['Industry_Growth_Rate', 'Sector_Volatility_Beta', 'Commodity_Exposure_Index', 
                     'Supply_Chain_Risk_Score', 'Sector_News_Sentiment']
    df = create_missing_flags(df, industry_cols)
    
    pressure_map = {'Low': 1, 'Medium': 2, 'High': 3, 'Severe': 4, 'Critical': 5}
    numeric_pressure = df['Regulatory_Pressure'].map(pressure_map).fillna(2)
    
    df['Industry_Headwind'] = (df['Industry_Growth_Rate'] < 0.05).astype(int)
    df['Industry_Contraction'] = (df['Industry_Growth_Rate'] < 0).astype(int)
    df['Industry_Stagnant'] = ((df['Industry_Growth_Rate'] >= 0) & (df['Industry_Growth_Rate'] < 0.03)).astype(int)
    
    df['Sector_High_Volatility'] = (df['Sector_Volatility_Beta'] > 1.2).astype(int)
    df['Sector_Very_High_Volatility'] = (df['Sector_Volatility_Beta'] > 1.5).astype(int)
    df['Sector_Stable'] = (df['Sector_Volatility_Beta'] < 0.8).astype(int)
    
    df['Regulatory_Risk_Amplified'] = ((df['Regulatory_Action_Flag'] == 1) & (numeric_pressure > numeric_pressure.median())).astype(int)
    df['Supply_Chain_Stressed'] = (df['Supply_Chain_Risk_Score'] > 60).astype(int)
    df['Supply_Chain_Critical'] = (df['Supply_Chain_Risk_Score'] > 80).astype(int)
    df['Commodity_Exposure_High'] = (df['Commodity_Exposure_Index'] > 0.60).astype(int)
    df['Commodity_Exposure_Extreme'] = (df['Commodity_Exposure_Index'] > 0.80).astype(int)
    
    df['Sector_Sentiment_Headwind'] = (df['Sector_News_Sentiment'] < -0.40).astype(int)
    df['Sector_Sentiment_Neutral'] = ((df['Sector_News_Sentiment'] >= -0.40) & (df['Sector_News_Sentiment'] <= 0.40)).astype(int)
    df['Sector_Sentiment_Tailwind'] = (df['Sector_News_Sentiment'] > 0.40).astype(int)
    
    df['Industry_Risk_Score'] = (
        df['Industry_Headwind'] * 15 + df['Sector_High_Volatility'] * 15 +
        df['Regulatory_Risk_Amplified'] * 20 + df['Supply_Chain_Stressed'] * 15 +
        df['Commodity_Exposure_High'] * 12 + df['Sector_Sentiment_Headwind'] * 10
    ) / 100
    
    df = apply_anomaly_detection(df, industry_cols, 'Ind')
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df = scale_numeric_features(df, numeric_cols, method='robust')
    print(f"  [M3 PREPROCESSING] Complete!\n")
    return df

# =============================================================================
# MODEL 4: UNSTRUCTURED/TEXT DATA PREPROCESSING
# =============================================================================
def preprocess_text_data(df_unst):
    df = df_unst.copy()
    print("\n  [M4 PREPROCESSING] Starting text/unstructured preprocessing...")
    
    text_cols = ['Litigation_Count', 'Fraud_Keywords_Count', 'Negative_News_Sentiment',
                 'NCLT_Active_Flag', 'Promoter_Disputes_Flag', 'Governance_Issues_Flag',
                 'Related_Party_Anomaly_Flag', 'DIN_Disqualification_Flag',
                 'Auditor_Qualified_Opinion_Flag', 'SARFAESI_Action_Flag']
    
    df = create_missing_flags(df, text_cols)
    
    df['Litigation_Chronic'] = (df['Litigation_Count'] > 2).astype(int)
    df['Litigation_Severe'] = (df['Litigation_Count'] > 5).astype(int)
    df['Litigation_Risk_Score'] = np.minimum(df['Litigation_Count'] / 10, 1.0)
    df['NCLT_Critical'] = df['NCLT_Active_Flag'].astype(int)
    df['SARFAESI_Active'] = df['SARFAESI_Action_Flag'].astype(int)
    df['Distressed_Proceedings'] = ((df['NCLT_Active_Flag'] == 1) | (df['SARFAESI_Action_Flag'] == 1)).astype(int)
    
    df['Fraud_Keywords_Present'] = (df['Fraud_Keywords_Count'] > 0).astype(int)
    df['Fraud_Keywords_Multiple'] = (df['Fraud_Keywords_Count'] > 2).astype(int)
    df['Fraud_Risk_Score'] = np.minimum(df['Fraud_Keywords_Count'] / 5, 1.0)
    
    df['Governance_Critical'] = df['Governance_Issues_Flag'].astype(int)
    df['RPT_Anomaly_Flag'] = df['Related_Party_Anomaly_Flag'].astype(int)
    df['Promoter_Dispute_Flag'] = df['Promoter_Disputes_Flag'].astype(int)
    df['DIN_Disqualified_Flag'] = df['DIN_Disqualification_Flag'].astype(int)
    
    df['Governance_Risk_Score'] = (df['Governance_Issues_Flag'] * 0.25 + df['Related_Party_Anomaly_Flag'] * 0.25 + df['Promoter_Disputes_Flag'] * 0.25 + df['DIN_Disqualification_Flag'] * 0.25)
    df['Auditor_Qualification_Flag'] = df['Auditor_Qualified_Opinion_Flag'].astype(int)
    df['Negative_News_Severe'] = (df['Negative_News_Sentiment'] < -0.60).astype(int)
    df['Negative_News_High'] = (df['Negative_News_Sentiment'] < -0.30).astype(int)
    
    df['Character_Risk_Score'] = (
        df['NCLT_Active_Flag'] * 25 + df['SARFAESI_Action_Flag'] * 20 +
        df['Fraud_Keywords_Present'] * 20 + df['Governance_Issues_Flag'] * 15 +
        df['Related_Party_Anomaly_Flag'] * 15 + df['DIN_Disqualification_Flag'] * 12 +
        df['Auditor_Qualified_Opinion_Flag'] * 10 + df['Promoter_Disputes_Flag'] * 10 +
        df['Negative_News_Severe'] * 8
    ) / 155
    
    df = apply_anomaly_detection(df, text_cols, 'Text')
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df = scale_numeric_features(df, numeric_cols, method='robust')
    print(f"  [M4 PREPROCESSING] Complete!\n")
    return df