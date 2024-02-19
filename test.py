import logging
import json
import boto3

from PIL import Image
import torch
from transformers import Blip2Processor, Blip2ForConditionalGeneration

processor = Blip2Processor.from_pretrained("./model")
model = Blip2ForConditionalGeneration.from_pretrained("./model")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model.to(device)