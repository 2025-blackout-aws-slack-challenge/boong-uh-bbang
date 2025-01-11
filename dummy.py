import json
import boto3

lambda_client = boto3.client("lambda")

WORKER_LAMBDA_NAME = "blackout-6-python-test"


def lambda_handler(event, context):
    body = json.loads(event["body"])

    event_type = body["type"]

    # 슬랙의 URL 검증 처리
    if event_type == "url_verification":
        return {"statusCode": 200, "body": json.dumps({"challenge": body["challenge"]})}

    response = {
        "statusCode": 200,
        "body": "Request received. Processing asynchronously.",
    }

    try:
        lambda_client.invoke(
            FunctionName=WORKER_LAMBDA_NAME,
            InvocationType="Event",
            Payload=json.dumps(event),
        )
    except Exception as e:
        print("Error invoking worker lambda:", e)

    return response
