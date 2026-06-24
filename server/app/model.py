import torch
import joblib
import numpy as np
from torchvision import models
from torchvision import transforms
from PIL import Image
import torch

def predict_soil_type(image_path, model, transform, class_names):
    model.eval()

    image = Image.open(image_path).convert('RGB')
    image_tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(image_tensor)
        _, predicted = torch.max(output, 1)

    soil_idx = predicted.item()
    soil_name = class_names[soil_idx]

    return soil_idx, soil_name


def integrated_crop_recommendation_efficientnet_lgb(
    soil_image_path,
    soil_numerical_values,
    efficientnet_model,
    transform,
    soil_classes,
    scaler,
    lgb_model,
    label_encoder,
    device
):
    # 1. Predict soil
    soil_idx, soil_name = predict_soil_type(
        soil_image_path,
        efficientnet_model,
        transform,
        soil_classes
    )

    print("Predicted Soil:", soil_name)

    # 2. Scale numbers
    soil_numerical_values = np.array(soil_numerical_values).reshape(1, 7)
    num_scaled = scaler.transform(soil_numerical_values)

    # 3. One-hot soil
    soil_onehot = np.zeros((1, len(soil_classes)))
    soil_onehot[0, soil_idx] = 1

    # 4. Combine
    final_input = np.concatenate([num_scaled, soil_onehot], axis=1).astype(np.float32)

    # 5. Predict crop
    y_pred = lgb_model.predict(final_input)
    crop_name = label_encoder.inverse_transform(y_pred)[0]

    print("Predicted Crop:", crop_name)

    return crop_name, soil_name


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load soil classes
soil_classes = np.load("model/saved_models/soil_classes.npy", allow_pickle=True)

# Rebuild EfficientNet architecture
efficientnet_model = models.efficientnet_b0(weights=None)
efficientnet_model.classifier[1] = torch.nn.Linear(
    efficientnet_model.classifier[1].in_features,
    len(soil_classes)
)

test_transforms = transforms.Compose([
    transforms.Resize((224,224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

# Load weights
efficientnet_model.load_state_dict(torch.load("model/saved_models/efficientnet.pth", map_location=device))
efficientnet_model.to(device)
efficientnet_model.eval()

# Load LightGBM
lgb_model = joblib.load("model/saved_models/lgb_model.pkl")

# Load scaler + label encoder
scaler = joblib.load("model/saved_models/scaler.pkl")
le = joblib.load("model/saved_models/label_encoder.pkl")

print("Models loaded successfully")
print("Soil classes:", soil_classes)
print("LightGBM ready:", lgb_model)

# ---------------------------
# MANUAL TEST INPUT
# ---------------------------

soil_image = "model/soil-image-dataset/test/Black Soil/Black_1.jpg"

numerical = [[
    78,    # Nitrogen
    36,    # Phosphorus
    42,    # Potassium
    27.5,  # Temperature
    68,    # Humidity
    6.4,   # pH
    185    # Rainfall
]]

# ---------------------------
# RUN PREDICTION
# ---------------------------

crop, soil = integrated_crop_recommendation_efficientnet_lgb(
    soil_image_path=soil_image,
    soil_numerical_values=numerical,
    efficientnet_model=efficientnet_model,
    transform=test_transforms,     # MUST be defined
    soil_classes=soil_classes,     # loaded from .npy
    scaler=scaler,
    lgb_model=lgb_model,
    label_encoder=le,
    device=device
)

print("\nFINAL RESULT")
print("Detected Soil:", soil)
print("Recommended Crop:", crop)
