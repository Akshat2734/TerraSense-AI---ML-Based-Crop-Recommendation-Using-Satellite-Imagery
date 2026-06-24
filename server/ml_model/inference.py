import torch
import joblib
import numpy as np
from torchvision import models, transforms
from PIL import Image

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load soil classes
soil_classes = np.load("ml_model/saved_models/soil_classes.npy", allow_pickle=True)

# Build EfficientNet
efficientnet_model = models.efficientnet_b0(weights=None)
efficientnet_model.classifier[1] = torch.nn.Linear(
    efficientnet_model.classifier[1].in_features,
    len(soil_classes)
)

efficientnet_model.load_state_dict(
    torch.load("ml_model/saved_models/efficientnet.pth", map_location=device)
)

efficientnet_model.to(device)
efficientnet_model.eval()

# Load LightGBM pipeline
lgb_model = joblib.load("ml_model/saved_models/lgb_model.pkl")
scaler = joblib.load("ml_model/saved_models/scaler.pkl")
label_encoder = joblib.load("ml_model/saved_models/label_encoder.pkl")

# Image transform
transform = transforms.Compose([
    transforms.Resize((224,224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485,0.456,0.406],
        std=[0.229,0.224,0.225]
    )
])


def predict_soil(image_path):

    image = Image.open(image_path).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        output = efficientnet_model(tensor)
        _, predicted = torch.max(output, 1)

    soil_idx = predicted.item()
    soil_name = soil_classes[soil_idx]

    return soil_idx, soil_name


def predict_crop(image_path, numerical_values):

    soil_idx, soil_name = predict_soil(image_path)

    numerical_values = np.array(numerical_values).reshape(1,7)
    num_scaled = scaler.transform(numerical_values)

    soil_onehot = np.zeros((1,len(soil_classes)))
    soil_onehot[0, soil_idx] = 1

    final_input = np.concatenate(
        [num_scaled, soil_onehot],
        axis=1
    ).astype(np.float32)

    y_pred = lgb_model.predict(final_input)

    crop_name = label_encoder.inverse_transform(y_pred)[0]

    return soil_name, crop_name