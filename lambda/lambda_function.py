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
VALID_STATUS = ("available", "borrowed", "maintenance")
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

            names = {f"#{k}": k for k in fields}
            values = {f":{k}": v for k, v in fields.items()}
            expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)

            result = table.update_item(
                Key={"id": item_id},
                UpdateExpression=expr,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ConditionExpression="attribute_exists(id)",
                ReturnValues="ALL_NEW",
            )
            return response(200, result["Attributes"])

        # DELETE
        if method == "DELETE" and item_id:
            table.delete_item(Key={"id": item_id})
            return response(200, {"deleted": item_id})

        return response(400, {"error": "unsupported request"})

    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return response(404, {"error": "equipment not found"})
    except json.JSONDecodeError:
        return response(400, {"error": "invalid JSON body"})
    except Exception as e:
        print("ERROR:", str(e))
        return response(500, {"error": "internal server error"})
