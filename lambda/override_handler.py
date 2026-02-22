"""
AWS Lambda handler for override requests.
"""
import json
import logging
import sys
sys.path.insert(0, '/var/task')

from src.api.handlers import OverrideHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

handler = OverrideHandler()

def lambda_handler(event, context):
    logger.info(f"Received override event: {json.dumps(event)}")
    
    if "body" in event:
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except json.JSONDecodeError:
            return format_response(400, {"error": "Invalid JSON body"})
    else:
        body = event
    
    result = handler.handle_override(body)
    return format_response(result.pop("status_code"), result)

def format_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body)
    }
