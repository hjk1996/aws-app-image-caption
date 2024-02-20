from transformers import BlipProcessor, BlipForConditionalGeneration, AutoTokenizer, AutoModel

processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-large"
)

processor.save_pretrained("./model")
model.save_pretrained("./model")


tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L12-v2")
model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L12-v2")

tokenizer.save_pretrained("./embedding_model")
model.save_pretrained("./embedding_model")