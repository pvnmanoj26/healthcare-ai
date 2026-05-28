from adapters.bigquery import run_bigquery_query as run_bq_query

def run_bigquery_query(sql: str) -> dict:
    """
    Run a SQL query against the BigQuery healthcare dataset.
    Returns rows matching the query.
    """
    return run_bq_query(sql)
