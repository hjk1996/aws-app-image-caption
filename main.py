import os
import io
import logging
import json
import boto3
import time

from PIL import Image, UnidentifiedImageError
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

from errors import S3ImageDoesNotExistError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


logging.info("Loading Model")


# Initialize AWS services
sqs = boto3.client("sqs")
queue_url = os.environ["SQS_URL"]


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

logging.info("AWS services initialized")

logging.info("Loading Model")
# Load the model
processor = BlipProcessor.from_pretrained("./model")
model = BlipForConditionalGeneration.from_pretrained("./model")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


def download_image_from_s3(bucket_name, object_key) -> Image.Image:
    try:
        file_stream = io.BytesIO()
        s3.download_fileobj(bucket_name, object_key, file_stream)
        file_stream.seek(0)
        return Image.open(file_stream)
    except Exception as e:
        raise S3ImageDoesNotExistError(f"Image {object_key} does not exist in S3.")


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

        image = download_image_from_s3(bucket_name, object_key)

        inputs = processor(images=image, return_tensors="pt").to(device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=300,
            top_k=50,  # 확률 순위가 50위 밖인 토큰은 샘플링에서 제외
            top_p=0.95,  # 누적 확률이 95%인 후보집합에서만 생성
            do_sample=True,  # 샘플링 전략 사용
        )
        caption = processor.decode(outputs[0], skip_special_tokens=True)
        logging.info(f"Image {object_key} processed. Caption: {caption}")
        return {
            "user_id": user_id,
            "file_name": file_name,
            "caption": caption,
        }
    except json.JSONDecodeError as e:
        logging.error(f"[{type(e)}]: Failed to decode JSON message.")
    except KeyError as e:
        logging.error(f"[{type(e)}]: Missing key in message: {e}")
    except UnidentifiedImageError:
        logging.error(f"[{type(e)}]: Failed to identify image: {object_key}")
    except S3ImageDoesNotExistError as e:
        logging.error(f"[{type(e)}]: Image {object_key} does not exist in S3.")
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])

    except Exception as e:
        logging.error(f"[{type(e)}]: Unexpected error: {e}")


def poll_sqs_messages():
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20
            )
            messages = response.get("Messages", [])

            if not messages:
                logging.info("No messages to process. Sleeping for 5 seconds.")
                time.sleep(5)
                continue

            captions = []
            entries = []
            for message in messages:
                caption = process_image_message(message)
                # Delete the message from the queue
                if caption:
                    captions.append(caption)
                    entries.append(
                        {
                            "Id": message["MessageId"],
                            "ReceiptHandle": message["ReceiptHandle"],
                        }
                    )

            if captions:
                with table.batch_writer() as writer:
                    for caption in captions:
                        writer.put_item(Item=caption)
                logging.info(f"Added {len(captions)} items to the DynamoDB table.")
                sqs.delete_message_batch(QueueUrl=queue_url, Entries=entries)
                logging.info(f"Deleted {len(entries)} messages from the queue.")

        except Exception as e:
            logging.error(f"{[type(e)]}: Error polling SQS messages: {e}")


if __name__ == "__main__":
    logging.info("Starting the process.")
    try:
        poll_sqs_messages()
    except KeyboardInterrupt as e:
        logging.info(f"[{type(e)}]: Process interrupted by user.")
    except Exception as e:
        logging.error(f"[{type(e)}]: Unexpected error: {e}")
