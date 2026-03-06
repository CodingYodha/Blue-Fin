import httpx
import asyncio
import duckdb
import os
import json
import logging
from dataclasses import dataclass

from utils import validate_job_id

logger = logging.getLogger(__name__)

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
DATABRICKS_SQL_WAREHOUSE = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID")
DATABRICKS_TIMEOUT = 8.0  # seconds — V7 fix

class DatabricksError(Exception): pass
class DuckDBFallbackError(Exception): pass

@dataclass
class GoFeatures:
    gst_filing_delay_days: float = 0.0
    gst_vs_bank_variance_pct: float = 0.0
    gstr_2a_3b_itc_mismatch_pct: float = 0.0
    historical_defaults: float = 0.0
    rating_downgrades_count: float = 0.0
    payment_delays_days: float = 0.0
    tax_compliance_score: float = 0.0
    round_trip_transaction_count: float = 0.0
    cash_deposit_ratio: float = 0.0
    gst_scrutiny_notice_flag: float = 0.0
    industry_growth_rate: float = 0.0
    sector_volatility_beta: float = 0.0
    regulatory_pressure: str = "Medium"
    commodity_exposure_index: float = 0.0
    supply_chain_risk_score: float = 0.0
    regulatory_action_flag: float = 0.0
    
    _backend: str = "unknown"

    def get(self, key, default=None):
        return getattr(self, key, default)

def safe_cast(k: str, v: any) -> any:
    if k == "regulatory_pressure":
        return str(v) if v is not None else "Medium"
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

async def read_from_databricks(job_id: str) -> dict:
    """
    Queries Databricks SQL Warehouse for Go service fraud features.
    """
    sql = """
    SELECT
        gst_filing_delay_days,
        gst_vs_bank_variance_pct,
        gstr_2a_3b_itc_mismatch_pct,
        historical_defaults,
        rating_downgrades_count,
        payment_delays_days,
        tax_compliance_score,
        round_trip_transaction_count,
        cash_deposit_ratio,
        gst_scrutiny_notice_flag,
        industry_growth_rate,
        sector_volatility_beta,
        regulatory_pressure,
        commodity_exposure_index,
        supply_chain_risk_score,
        regulatory_action_flag
    FROM intelli_credit.fraud_features
    WHERE job_id = :job_id
    LIMIT 1
    """

    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "warehouse_id": DATABRICKS_SQL_WAREHOUSE,
        "statement": sql,
        "wait_timeout": "7s",
        "parameters": [{"name": "job_id", "value": job_id, "type": "STRING"}]
    }

    async with httpx.AsyncClient(timeout=DATABRICKS_TIMEOUT) as client:
        response = await client.post(
            f"{DATABRICKS_HOST}/api/2.0/sql/statements",
            json=payload, headers=headers
        )

    if response.status_code != 200:
        raise DatabricksError(f"HTTP {response.status_code}")

    data = response.json()
    rows = data.get("result", {}).get("data_array", [])
    if not rows:
        raise DatabricksError("No fraud features found for job_id")

    columns = [c["name"] for c in data["manifest"]["schema"]["columns"]]
    return dict(zip(columns, rows[0]))

def read_from_duckdb(job_id: str) -> dict:
    parquet_path = f"/tmp/intelli-credit/{job_id}/fraud_features.parquet"
    if not os.path.exists(parquet_path):
        json_path = f"/tmp/intelli-credit/{job_id}/fraud_features.json"
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                return json.load(f)
        raise DuckDBFallbackError("No local fraud features found")

    conn = duckdb.connect(":memory:")
    result = conn.execute(
        "SELECT * FROM read_parquet(?) LIMIT 1",
        [parquet_path]
    ).fetchdf()
    return result.iloc[0].to_dict()

async def read_go_features(job_id: str) -> GoFeatures:
    """
    Try Databricks first. On timeout or error, fall back to DuckDB.
    Log which backend was used.
    """
    validate_job_id(job_id)
    try:
        data = await read_from_databricks(job_id)
        logger.info(f"Go features read from Databricks for {job_id}")
        backend = "databricks"
    except (httpx.TimeoutException, DatabricksError, Exception) as e:
        logger.warning(
            f"Databricks unavailable ({e}). "
            f"Failing over to local DuckDB execution..."
        )
        try:
            data = read_from_duckdb(job_id)
            backend = "duckdb_fallback"
        except Exception as fallback_e:
            logger.error(f"DuckDB fallback failed: {fallback_e}")
            data = {}
            backend = "empty_fallback"

    valid_keys = {f.name for f in GoFeatures.__dataclass_fields__.values()}
    filtered_data = {k: safe_cast(k, v) for k, v in data.items() if k in valid_keys}
    
    features = GoFeatures(**filtered_data)
    features._backend = backend
    return features
