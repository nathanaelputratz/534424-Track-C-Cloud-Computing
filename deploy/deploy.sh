#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
BUCKET_NAME="${1:-${BUCKET_NAME:-lab-equipment-data}}"
FUNCTION_NAME="${FUNCTION_NAME:-lab-equipment-handler}"
CONCURRENCY="${CONCURRENCY:-5}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAMBDA_SRC="${REPO_ROOT}/lambda/lambda_function.py"

if [ ! -f "$LAMBDA_SRC" ]; then
  echo "Error: ${LAMBDA_SRC} not found."
  exit 1
fi

ZIP_FILE="$(mktemp /tmp/lab-equipment-handler-XXXXXX.zip)"
trap 'rm -f "$ZIP_FILE"' EXIT

echo "1. Verifying AWS identity"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/LabRole"
echo "Account ID : ${ACCOUNT_ID}"
echo "Region     : ${REGION}"
echo "Role ARN   : ${ROLE_ARN}"
echo

echo "2. Creating/checking S3 bucket (${BUCKET_NAME})"
if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
  echo "Bucket ${BUCKET_NAME} already exists."
else
  aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" >/dev/null
  echo "Created bucket ${BUCKET_NAME}."
fi

aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
echo "Block Public Access enabled."
echo

echo "3. Packaging Lambda code"
python3 - "$LAMBDA_SRC" "$ZIP_FILE" <<'PY'
import sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(src, arcname="lambda_function.py")
PY
echo "Packaged ${LAMBDA_SRC}."
echo

echo "4. Creating/updating Lambda function (${FUNCTION_NAME})"
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Function exists, updating code and configuration..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://${ZIP_FILE}" \
    --region "$REGION" >/dev/null
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --timeout 10 \
    --environment "Variables={BUCKET_NAME=${BUCKET_NAME}}" \
    --region "$REGION" >/dev/null
else
  echo "Creating new Lambda function..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --role "$ROLE_ARN" \
    --handler lambda_function.lambda_handler \
    --timeout 10 \
    --environment "Variables={BUCKET_NAME=${BUCKET_NAME}}" \
    --zip-file "fileb://${ZIP_FILE}" \
    --region "$REGION" >/dev/null
fi

aws lambda wait function-active-v2 \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"
echo "Lambda function is active."
echo

echo "5. Setting reserved concurrency (${CONCURRENCY})"
if aws lambda put-function-concurrency \
  --function-name "$FUNCTION_NAME" \
  --reserved-concurrent-executions "$CONCURRENCY" \
  --region "$REGION" >/dev/null 2>&1; then
  echo "Reserved concurrency set to ${CONCURRENCY}."
else
  echo "Warning: could not set reserved concurrency (skipping)."
fi
echo

echo "6. Configuring Lambda Function URL"
FUNCTION_URL=$(aws lambda get-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --query FunctionUrl \
  --output text 2>/dev/null || true)

if [ -z "$FUNCTION_URL" ] || [ "$FUNCTION_URL" = "None" ]; then
  FUNCTION_URL=$(aws lambda create-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --auth-type NONE \
    --region "$REGION" \
    --query FunctionUrl \
    --output text)
fi

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id FunctionURLAllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" >/dev/null 2>&1 || true

FUNCTION_URL="${FUNCTION_URL%/}"
echo "Deployment complete!"
echo "Function URL: ${FUNCTION_URL}"
echo
echo "Test with:"
echo "  ./tests/test-api.sh ${FUNCTION_URL}"
