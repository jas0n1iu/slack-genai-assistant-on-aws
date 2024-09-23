import json
import boto3
import os
import urllib3
import re
import random
import base64
import uuid
from botocore.response import StreamingBody
from botocore.exceptions import ClientError
import hmac
import hashlib
import time
import decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('table_name'))

# Initialize AWS clients for Bedrock, Secrets Manager, and Parameter Store
bedrock_runtime_client = boto3.client('bedrock-runtime')
secretsmanager_client = boto3.client('secretsmanager')
s3_client = boto3.client('s3')

# Fetch the Slack token and API URL from Secrets Manager and Parameter Store
slack_token = json.loads(
    secretsmanager_client.get_secret_value(
        SecretId=os.environ.get('slack_token')
    )['SecretString']
)['token']

slack_api_url = 'https://slack.com/api/chat.postMessage'

# Fetch the Slack signing secret from Secrets Manager
slack_signing_secret = json.loads(
    secretsmanager_client.get_secret_value(
        SecretId=os.environ.get('slack_signing_secret')
    )['SecretString']
)['secret']

http = urllib3.PoolManager()

# Set the S3 bucket name and prefix for storing images
S3_BUCKET_NAME = os.environ.get('s3_bucket')
CLOUDFRONT_NAME = os.environ.get('cloudfront')
S3_PREFIX = 'images/'


# Slack signature verification
def verify_slack_signature(headers, body):
    slack_signature = headers.get('x-slack-signature', '')
    slack_timestamp = headers.get('x-slack-request-timestamp', '')

    base_string = f"v0:{slack_timestamp}:{body}"
    computed_signature = "v0=" + hmac.new(
        bytes(slack_signing_secret, "utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_signature, slack_signature)

def handle_message(slack_body):
    slack_text = slack_body.get('event').get('text')
    slack_user = slack_body.get('event').get('user')
    channel = slack_body.get('event').get('channel')

    pattern = r'<@\w+>\s*(.+)'
    match = re.search(pattern, slack_body.get('event').get('text'))

    if match:
        slack_text = match.group(1)
    else:
        print("No match found.")

    image_url = call_bedrock(slack_text)

    data = {
        'channel': channel,
        'blocks': [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{slack_user}> Generated Image:"
                }
            },
            {
                "type": "image",
                "image_url": image_url,
                "alt_text": "Generated Image"
            }
        ]
    }

    headers = {
        'Authorization': f'Bearer {slack_token}',
        'Content-Type': 'application/json',
    }

    # Send message to the Slack API
    try:
        http.request(
            'POST',
            slack_api_url,
            headers=headers,
            body=json.dumps(data)
        )
    except Exception as e:
        print(f"Error sending message to Slack: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Error sending message to Slack'})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({'msg': "message received"})
    }


def call_bedrock(question):
    """
    Calls the Bedrock AI model with the given question.

    Args:
        question (str): The question to ask the Bedrock AI model.

    Returns:
        str: The URL of the generated image.
    """
    # Create a Bedrock Runtime client in the AWS Region of your choice.
    client = boto3.client("bedrock-runtime")

    # Set the model ID, e.g., Stable Diffusion XL 1.
    model_id = "stability.stable-diffusion-xl-v1"

    # Define the image generation prompt for the model.
    # prompt = "A stylized picture of a cute old steampunk robot."

    # Generate a random seed.
    seed = random.randint(0, 4294967295)

    # Format the request payload using the model's native structure.
    native_request = {
        "text_prompts": [{"text": question}],
        "style_preset": "photographic",
        "seed": seed,
        "cfg_scale": 10,
        "steps": 30,
    }

    # Convert the native request to JSON.
    request = json.dumps(native_request)

    # Invoke the model with the request.
    try:
        response = client.invoke_model(modelId=model_id, body=request)
    except Exception as e:
        print(f"Error calling Bedrock AI model: {e}")
        return "Sorry, I'm having trouble processing your request right now."

    # Decode the response body.
    model_response = json.loads(response["body"].read())

    # Extract the image data.
    base64_image_data = model_response["artifacts"][0]["base64"]

    # Upload the image to S3
    image_key = f"{S3_PREFIX}{str(uuid.uuid4())}.png"
    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=image_key,
        Body=base64.b64decode(base64_image_data),
        ContentType="image/png"
    )

    # Generate the image URL
    # image_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{image_key}"
    image_url = f"https://{CLOUDFRONT_NAME}/{image_key}"

    return image_url


def handler(event, context):
    event_body = json.loads(event.get("body"))
    response = None

    # Verify the Slack signature
    if not verify_slack_signature(event['headers'], event['body']):
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Invalid Slack signature'})
        }

    if event_body.get("type") == "url_verification":
        """
        Handles the Slack challenge event for verifying the URL.
        https://api.slack.com/events/url_verification
        """
        response = {
            'statusCode': 200,
            'body': event_body['challenge']
        }
    else:
        client_msg_id = event_body['event']['client_msg_id']
        try:
            table.put_item(
                Item={
                    'client_msg_id': client_msg_id,
                    'timestamp': int(time.time())  # Add a timestamp for replay attack prevention
                },
                ConditionExpression='attribute_not_exists(client_msg_id)'
            )

            response = handle_message(event_body)

        except ClientError as e:
            if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                return {
                    'statusCode': 200,
                    'body': json.dumps('Event already processed')
                }
    return response