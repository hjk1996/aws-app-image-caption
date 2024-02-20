FROM pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime
RUN pip install transformers boto3 Pillow
ENV SQS_URL=https://sqs.us-east-1.amazonaws.com/109412806537/image-caption-queue
ENV DYNAMODB_TABLE_NAME=AppImageCaption
WORKDIR /app
RUN mkdir /app/model
ADD download_model.py /app
RUN python download_model.py
ADD errors.py /app
ADD utils.py /app
ADD main.py /app
CMD ["python", "main.py"]
