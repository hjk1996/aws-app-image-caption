from PIL import Image

import torch
import torch.nn.functional as F

from errors import S3ImageDoesNotExistError


def get_sentence_embedding(tokenizer, embedding_model, device, sentence: str) -> torch.Tensor:
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
