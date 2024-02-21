import os
import asyncio
import logging
import json
import boto3
import time
import signal


from PIL import UnidentifiedImageError
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
import torch
import torch.nn.functional as F
from transformers import (
    BlipProcessor,
    BlipForConditionalGeneration,
    AutoTokenizer,
    AutoModel,
)

from utils import download_image_from_s3, get_sentence_embedding
from errors import S3ImageDoesNotExistError


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


logging.info("Loading Model")

# 종료 플래그를 정의합니다.
shutdown_flag = False


def signal_handler(signum, frame):
    global shutdown_flag
    logging.info("SIGTERM received, shutting down...")
    shutdown_flag = True


# SIGTERM 신호 핸들러를 등록합니다.
signal.signal(signal.SIGTERM, signal_handler)


# Initialize AWS services
sqs = boto3.client("sqs")
queue_url = os.environ["SQS_URL"]


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])
logging.info("AWS services initialized")


credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials=credentials, region=os.environ["AWS_REGION"])
os_client = OpenSearch(
    hosts=[{"host": os.environ["OPENSEARCH_ENDPOINT"]}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)
logging.info("OpenSearch client initialized")


logging.info("Loading Image Caption Model")
# Load the model
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-large"
)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

logging.info("Loading Sentence Embedding Model")
embedding_model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L12-v2")
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L12-v2")
embedding_model.to(device)


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

        image = download_image_from_s3(s3, bucket_name, object_key)

        inputs = processor(images=image, return_tensors="pt").to(device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=300,
        )
        caption = processor.decode(outputs[0], skip_special_tokens=True)
        logging.info(f"Image {object_key} processed. Caption: {caption}")
        caption_embedding = get_sentence_embedding(
            tokenizer, embedding_model, device, caption
        )
        caption_embedding = caption_embedding.squeeze().detach().cpu().tolist()
        return {
            "user_id": user_id,
            "file_name": file_name,
            "caption": caption,
            "caption_vector": caption_embedding,
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


async def update_dynamodb_table(table, data: dict[str, str]) -> bool:
    try:
        table.update_item(
            Key={"user_id": data["user_id"], "file_name": data["file_name"]},
            UpdateExpression="set caption = :c",
            ExpressionAttributeValues={":c": data["caption"]},
            ConditionExpression="attribute_exists(user_id) AND attribute_exists(file_name)",
            ReturnValues="ALL_NEW",
        )
        return True
    except Exception as e:
        logging.error(f"[{type(e)}]: Error updating DynamoDB table: {e}")
        return False


async def save_vector_to_opensearch(os_client: OpenSearch, data: dict) -> bool:
    try:
        response = os_client.index(
            index=os.environ["OPENSEARCH_INDEX"],
            body={
                "user_id": data["user_id"],
                "file_name": data["file_name"],
                "caption_vector": data["caption_vector"],
                "created_at": int(time.time()),
            },
        )
        
        return True
    except Exception as e:
        logging.error(f"[{type(e)}]: Error indexing document in OpenSearch: {e}")
        return False


async def update_table_and_save_vector(
    table, os_client: OpenSearch, data: dict[str, str]
) -> bool:
    result = await update_dynamodb_table(table, data)
    if result:
        result = await save_vector_to_opensearch(os_client, data)
    return result


async def main():
    logging.info("Starting the process.")
    while not shutdown_flag:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20
            )
            messages = response.get("Messages", [])

            if not messages:
                logging.info("No messages to process. Sleeping for 5 seconds.")
                await asyncio.sleep(5)
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
                results = await asyncio.gather(
                    *[
                        update_table_and_save_vector(
                            table=table, os_client=os_client, data=caption
                        )
                        for caption in captions
                    ]
                )
                logging.info(f"Added {sum(results)} items to the DynamoDB table.")

            valid_entries = [entry for entry, result in zip(entries, results) if result]

            if valid_entries:
                sqs.delete_message_batch(QueueUrl=queue_url, Entries=valid_entries)
                logging.info(f"Deleted {len(entries)} messages from the queue.")

        except KeyboardInterrupt as e:
            logging.info(f"[{type(e)}]: Process interrupted by user.")
        except Exception as e:
            logging.error(f"{[type(e)]}: Error polling SQS messages: {e}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
        logging.info("Program exited gracefully")
