import io
import json

import requests
import boto3
from botocore.exceptions import ClientError
from PIL import Image
import torch
import torch.nn.functional as F

from errors import S3ImageDoesNotExistError


def download_pem_file() -> bool:
    # URL에서 파일을 가져옵니다.
    response = requests.get(
        "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"
    )
    # HTTP 요청이 성공했는지 확인합니다 (상태 코드 200).
    if response.status_code == 200:
        # 파일을 쓰기 모드로 열고 내용을 기록합니다.
        with open("global-bundle.pem", "wb") as file:
            file.write(response.content)
        return True
    else:
        return False
        


def get_sentence_embedding(
    tokenizer, embedding_model, device, sentence: str
) -> torch.Tensor:
    inputs = tokenizer(
        sentence,
        return_tensors="pt",
        padding=True,
        truncation=True,
    ).to(device)
    with torch.no_grad():
        model_output = embedding_model(**inputs)
    sentence_embeddings = mean_pooling(model_output, inputs["attention_mask"])
    return F.normalize(sentence_embeddings, p=2, dim=1)


def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[
        0
    ]  # First element of model_output contains all token embeddings
    input_mask_expanded = (
        attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    )
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
        input_mask_expanded.sum(1), min=1e-9
    )


def download_image_from_s3(s3, bucket_name, object_key) -> Image.Image:
    try:
        file_stream = io.BytesIO()
        s3.download_fileobj(bucket_name, object_key, file_stream)
        file_stream.seek(0)
        return Image.open(file_stream)
    except Exception as e:
        raise S3ImageDoesNotExistError(f"Image {object_key} does not exist in S3.")


def get_secret() -> dict[str, str]:

    secret_name = "app-docdb-secret"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response["SecretString"]
    return json.loads(secret)
