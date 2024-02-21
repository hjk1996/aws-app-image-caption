FROM pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime
RUN pip install transformers boto3 Pillow pymongo
ENV SQS_URL=https://sqs.us-east-1.amazonaws.com/109412806537/image-caption-queue
ENV DYNAMODB_TABLE_NAME=AppImageCaption
ENV OPENSEARCH_ENDPOINT=https://5pmqemvn6b1li4yn88nk.us-east-1.aoss.amazonaws.com
WORKDIR /app
RUN mkdir /app/model
ADD download_model.py /app
RUN python download_model.py
ADD errors.py /app
ADD utils.py /app
ADD main.py /app
ADD global-bundle.pem /app
CMD ["python", "main.py"]
