import json
from typing import Any, Dict, List, Tuple

from services.db import get_db_connection
from utils.logger import logger


def _json_or_none(payload: Any):
    if payload is None:
        return None
    try:
        # Ensure JSON serializable
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return json.dumps({"_raw": str(payload)}, ensure_ascii=False)


def upsert_equity_raw_and_normalized(
    owner: str,
    device_id: str,
    records: List[Dict[str, Any]],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Insert raw rows idempotently and write normalized row into trades table.
    Returns (accepted_client_ids, errors).
    """
    accepted: List[str] = []
    errors: List[Dict[str, Any]] = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for r in records:
                client_id = (r.get("clientId") or "").strip()
                op = (r.get("op") or "upsert").strip()
                payload = r.get("payload") or {}
                if not client_id:
                    errors.append({"clientId": client_id, "error": "missing clientId"})
                    continue

                raw_sql = """
                INSERT INTO equity_trade_raw (owner, device_id, client_id, op, raw_json)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE received_at=CURRENT_TIMESTAMP
                """
                cursor.execute(raw_sql, (owner, device_id, client_id, op, _json_or_none(payload)))

                if op == "delete":
                    # Keep normalized row as-is; delete semantics are local-first.
                    accepted.append(client_id)
                    continue

                # Normalized fields (best-effort)
                norm = payload if isinstance(payload, dict) else {}
                cursor.execute(
                    """
                    INSERT INTO trades (device_id, client_id, owner, date, code, name, side, price, quantity, amount, amount_auto)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      device_id=VALUES(device_id),
                      date=VALUES(date),
                      code=VALUES(code),
                      name=VALUES(name),
                      side=VALUES(side),
                      price=VALUES(price),
                      quantity=VALUES(quantity),
                      amount=VALUES(amount),
                      amount_auto=VALUES(amount_auto)
                    """,
                    (
                        device_id,
                        client_id,
                        owner,
                        norm.get("date"),
                        norm.get("code"),
                        norm.get("name"),
                        norm.get("side"),
                        norm.get("price") or 0,
                        norm.get("quantity") or 0,
                        norm.get("amount") or 0,
                        norm.get("amountAuto") or norm.get("amount_auto") or "0",
                    ),
                )
                accepted.append(client_id)

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"sync equity failed: {e}")
        raise
    finally:
        conn.close()
    return accepted, errors


def upsert_crypto_raw_and_normalized(
    owner: str,
    device_id: str,
    records: List[Dict[str, Any]],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    accepted: List[str] = []
    errors: List[Dict[str, Any]] = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for r in records:
                client_id = (r.get("clientId") or "").strip()
                op = (r.get("op") or "upsert").strip()
                payload = r.get("payload") or {}
                if not client_id:
                    errors.append({"clientId": client_id, "error": "missing clientId"})
                    continue

                cursor.execute(
                    """
                    INSERT INTO crypto_trade_raw (owner, device_id, client_id, op, raw_json)
                    VALUES (%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE received_at=CURRENT_TIMESTAMP
                    """,
                    (owner, device_id, client_id, op, _json_or_none(payload)),
                )

                if op == "delete":
                    accepted.append(client_id)
                    continue

                norm = payload if isinstance(payload, dict) else {}
                cursor.execute(
                    """
                    INSERT INTO crypto_trades (device_id, client_id, owner, date, code, platform, side, price, quantity)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                      device_id=VALUES(device_id),
                      date=VALUES(date),
                      code=VALUES(code),
                      platform=VALUES(platform),
                      side=VALUES(side),
                      price=VALUES(price),
                      quantity=VALUES(quantity)
                    """,
                    (
                        device_id,
                        client_id,
                        owner,
                        norm.get("date"),
                        (norm.get("code") or "").upper(),
                        norm.get("platform"),
                        norm.get("side"),
                        norm.get("price") or 0,
                        norm.get("quantity") or 0,
                    ),
                )
                accepted.append(client_id)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"sync crypto failed: {e}")
        raise
    finally:
        conn.close()
    return accepted, errors

