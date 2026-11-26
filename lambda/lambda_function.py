import json
import os
import uuid
from datetime import datetime, timezone

import boto3

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

VALID_CATEGORY = (
    "microcontroller",
    "sensor",
    "measurement",
    "power",
    "component",
    "tool",
)
VALID_CONDITION = ("good", "fair", "damaged")

def response(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

def lambda_handler(event, context):
    method = event["requestContext"]["http"]["method"]
    item_id = (event.get("pathParameters") or {}).get("id")

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
            table.put_item(Item=item)
            return response(201, item)

        # READ
        if method == "GET":
            if item_id:
                result = table.get_item(Key={"id": item_id})
                if "Item" in result:
                    return response(200, result["Item"])
                return response(404, {"error": "equipment not found"})
            return response(200, table.scan()["Items"])

        return response(400, {"error": "unsupported request"})

    except json.JSONDecodeError:
        return response(400, {"error": "invalid JSON body"})
    except Exception as e:
        print("ERROR:", str(e))
        return response(500, {"error": "internal server error"})
