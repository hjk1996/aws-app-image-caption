import os
import io
import logging
import json
import boto3

from PIL import Image, UnidentifiedImageError
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

# Initialize AWS services
sqs = boto3.client("sqs")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sqs_url = os.environ["SQS_URL"]
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

# Load the model
processor = BlipProcessor.from_pretrained("./model")
model = BlipForConditionalGeneration.from_pretrained("./model")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


def process_image_message(message) -> bool:
    try:
        # Parse the message
        message_body = json.loads(message["Body"])
        s3_info = message_body["Records"][0]["s3"]
        bucket_name = s3_info["bucket"]["name"]
        object_key = s3_info["object"]["key"]

        attributes = object_key.split("/")
        file_name = attributes[-1]
        user_id = attributes[1]

        # Get the object from S3 and read it into memory
        file_stream = io.BytesIO()
        s3.download_fileobj(bucket_name, object_key, file_stream)
        file_stream.seek(0)  # Move to the start of the file-like object

        # Open the image directly from the in-memory bytes
        image = Image.open(file_stream)
        inputs = processor(images=image, return_tensors="pt").to(device)
        outputs = model.generate(**inputs)
        caption = processor.decode(outputs[0], skip_special_tokens=True)

        # Store the caption in DynamoDB
        response = table.put_item(
            Item={"file_name": file_name, "user_id": user_id, "caption": caption}
        )
        logging.info(f"Image {object_key} processed. Caption: {caption}")
        return True
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON message.")
        return False
    except KeyError as e:
        logging.error(f"Missing key in message: {e}")
        return False
    except UnidentifiedImageError:
        logging.error(f"Failed to identify image: {object_key}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False


def poll_sqs_messages():
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=sqs_url, MaxNumberOfMessages=10, WaitTimeSeconds=20
            )
            logging.info("Response: %s", response)
            messages = response.get("Messages", [])
            logging.info("Messages: %s", messages)
            if not messages:
                continue

            for message in messages:
                ok = process_image_message(message)
                # Delete the message from the queue
                if ok:
                    sqs.delete_message(
                        QueueUrl=sqs_url, ReceiptHandle=message["ReceiptHandle"]
                    )
        except Exception as e:
            logging.error(f"Error polling SQS messages: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        poll_sqs_messages()
    except KeyboardInterrupt:
        logging.info("Process interrupted by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
