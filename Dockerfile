FROM pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime
ENV SQS_URL=https://sqs.us-east-1.amazonaws.com/109412806537/image-caption-queue
ENV DYNAMODB_TABLE_NAME=AppImageCaption
RUN pip install transformers boto3 Pillow
WORKDIR /app
ADD main.py /app
ADD models /app/models
CMD ["python", "main.py"]