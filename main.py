import os
import io
import logging
import json
import boto3

from PIL import Image, UnidentifiedImageError
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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


def process_image_message(message) -> dict[str, str]:
    try:
        # Parse the message
        message_body = json.loads(message["Body"])
        # Additional parsing for the inner JSON string contained in the "Message" field
        inner_message_body = json.loads(message_body["Message"])

        # Now using inner_message_body for S3 info extraction
        s3_info = inner_message_body["Records"][0]["s3"]
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

        logger.info(f"Image {object_key} processed. Caption: {caption}")
        return {
            "user_id": user_id,
            "file_name": file_name,
            "caption": caption,
        }
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON message.")
    except KeyError as e:
        logger.error(f"Missing key in message: {e}")
    except UnidentifiedImageError:
        logger.error(f"Failed to identify image: {object_key}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


def poll_sqs_messages():
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=sqs_url, MaxNumberOfMessages=10, WaitTimeSeconds=20
            )
            messages = response.get("Messages", [])
            
            if not messages:
                continue
            
            captions = []
            entries = []
            for message in messages:
                caption = process_image_message(message)
                # Delete the message from the queue
                if caption:
                    captions.append(caption)
                    entries.append(
                        {"Id": message["MessageId"], "ReceiptHandle": message["ReceiptHandle"]}
                    )
            
            if captions:
                with table.batch_writer() as writer:
                    for caption in captions:
                        writer.put_item(Item=caption)
                logger.info(f"Added {len(captions)} items to the DynamoDB table.")
                sqs.delete_messages(Entries=entries)
                logger.info(f"Deleted {len(entries)} messages from the queue.")
            
        except Exception as e:
            logger.error(f"Error polling SQS messages: {e}")


if __name__ == "__main__":
    try:
        poll_sqs_messages()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
