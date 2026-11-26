import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
BUCKET_NAME = os.environ["BUCKET_NAME"]
PREFIX = "equipment/"

VALID_CATEGORY = (
    "microcontroller",
    "sensor",
    "measurement",
    "power",
    "component",
    "tool",
)
VALID_STATUS = ("available", "borrowed", "maintenance")
VALID_CONDITION = ("good", "fair", "damaged")


def response(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def item_key(item_id):
    return f"{PREFIX}{item_id}.json"


def parse_route(event):
    raw_path = (event.get("rawPath") or "").rstrip("/")
    if raw_path == "/equipment":
        return True, None
    if raw_path.startswith("/equipment/"):
        remainder = raw_path[len("/equipment/") :]
        if remainder and "/" not in remainder:
            return True, remainder
    return False, None


def get_equipment_item(item_id):
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=item_key(item_id))
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            return None
        raise


def save_equipment_item(item):
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=item_key(item["id"]),
        Body=json.dumps(item).encode("utf-8"),
        ContentType="application/json",
    )


def list_equipment_items():
    items = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=PREFIX):
        for entry in page.get("Contents", []):
            key = entry["Key"]
            if not key.endswith(".json"):
                continue
            obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            items.append(json.loads(obj["Body"].read().decode("utf-8")))
    return items


def lambda_handler(event, context):
    method = event["requestContext"]["http"]["method"]
    valid_route, item_id = parse_route(event)
    if not valid_route:
        return response(404, {"error": "route not found"})

    try:
        # CREATE
        if method == "POST" and not item_id:
            data = json.loads(event.get("body") or "{}")
            if not data.get("name") or not data.get("category"):
                return response(400, {"error": "name and category are required"})
            if data["category"] not in VALID_CATEGORY:
                return response(
                    400,
                    {
                        "error": (
                            "category must be microcontroller, sensor, "
                            "measurement, power, component, or tool"
                        )
                    },
                )
            condition = data.get("condition", "good")
            if condition not in VALID_CONDITION:
                return response(
                    400, {"error": "condition must be good, fair, or damaged"}
                )

            item = {
                "id": str(uuid.uuid4()),
                "name": data["name"],
                "category": data["category"],
                "assetTag": data.get("assetTag", ""),
                "condition": condition,
                "status": "available",
                "borrower": "",
                "dueDate": "",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            save_equipment_item(item)
            return response(201, item)

        # READ
        if method == "GET":
            if item_id:
                item = get_equipment_item(item_id)
                if item is not None:
                    return response(200, item)
                return response(404, {"error": "equipment not found"})
            return response(200, list_equipment_items())

        # UPDATE
        if method == "PUT" and item_id:
            data = json.loads(event.get("body") or "{}")
            allowed = (
                "name",
                "category",
                "assetTag",
                "condition",
                "status",
                "borrower",
                "dueDate",
            )
            fields = {k: data[k] for k in allowed if k in data}
            if not fields:
                return response(400, {"error": "no valid fields to update"})
            if "category" in fields and fields["category"] not in VALID_CATEGORY:
                return response(
                    400,
                    {
                        "error": (
                            "category must be microcontroller, sensor, "
                            "measurement, power, component, or tool"
                        )
                    },
                )
            if "status" in fields and fields["status"] not in VALID_STATUS:
                return response(
                    400,
                    {"error": "status must be available, borrowed, or maintenance"},
                )
            if "condition" in fields and fields["condition"] not in VALID_CONDITION:
                return response(
                    400, {"error": "condition must be good, fair, or damaged"}
                )
            if fields.get("status") == "borrowed" and not fields.get("borrower"):
                return response(
                    400, {"error": "borrower is required when status is borrowed"}
                )
            if fields.get("status") in ("available", "maintenance"):
                fields["borrower"] = ""
                fields["dueDate"] = ""

            existing = get_equipment_item(item_id)
            if existing is None:
                return response(404, {"error": "equipment not found"})

            existing.update(fields)
            save_equipment_item(existing)
            return response(200, existing)

        # DELETE
        if method == "DELETE" and item_id:
            s3.delete_object(Bucket=BUCKET_NAME, Key=item_key(item_id))
            return response(200, {"deleted": item_id})

        return response(400, {"error": "unsupported request"})

    except json.JSONDecodeError:
        return response(400, {"error": "invalid JSON body"})
    except Exception as e:
        print("ERROR:", str(e))
        return response(500, {"error": "internal server error"})
