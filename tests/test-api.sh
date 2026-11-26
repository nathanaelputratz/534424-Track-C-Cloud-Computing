#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <INVOKE_URL>"
  echo "Example: $0 https://abc123.execute-api.us-east-1.amazonaws.com"
  exit 1
fi

BASE_URL="${1%/}"

echo "1. CREATE (POST /equipment)"
CREATE_RESP=$(curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE_URL}/equipment" \
  -H "Content-Type: application/json" \
  -d '{"name":"Arduino Uno R3","category":"microcontroller","assetTag":"LAB-ARD-001","condition":"good"}')
echo "$CREATE_RESP"

ITEM_ID=$(echo "$CREATE_RESP" | head -n 1 | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "Created ID: ${ITEM_ID}"
echo

echo "2. READ ALL (GET /equipment)"
curl -sS -w "\nHTTP %{http_code}\n" "${BASE_URL}/equipment"
echo

echo "3. READ ONE (GET /equipment/${ITEM_ID})"
curl -sS -w "\nHTTP %{http_code}\n" "${BASE_URL}/equipment/${ITEM_ID}"
echo

echo "4. UPDATE - BORROW (PUT /equipment/${ITEM_ID})"
curl -sS -w "\nHTTP %{http_code}\n" -X PUT "${BASE_URL}/equipment/${ITEM_ID}" \
  -H "Content-Type: application/json" \
  -d '{"status":"borrowed","borrower":"Rina","dueDate":"2026-12-10"}'
echo

echo "5. UPDATE - RETURN (PUT /equipment/${ITEM_ID})"
curl -sS -w "\nHTTP %{http_code}\n" -X PUT "${BASE_URL}/equipment/${ITEM_ID}" \
  -H "Content-Type: application/json" \
  -d '{"status":"available"}'
echo

echo "6. UPDATE - MAINTENANCE (PUT /equipment/${ITEM_ID})"
curl -sS -w "\nHTTP %{http_code}\n" -X PUT "${BASE_URL}/equipment/${ITEM_ID}" \
  -H "Content-Type: application/json" \
  -d '{"status":"maintenance","condition":"damaged"}'
echo

echo "7. DELETE (DELETE /equipment/${ITEM_ID})"
curl -sS -w "\nHTTP %{http_code}\n" -X DELETE "${BASE_URL}/equipment/${ITEM_ID}"
echo

echo "8. VERIFY DELETED (GET /equipment/${ITEM_ID})"
curl -sS -w "\nHTTP %{http_code}\n" "${BASE_URL}/equipment/${ITEM_ID}"
echo
