import cv2
import json
import os
import sys
import numpy as np

# Add src to path
sys.path.append(os.path.abspath("src"))

from deteccion_esquinas import obtener_mascara_roi_solida
from deteccion_bolsas import detectar_bolsas_cv

def debug_masks(img_name):
    img_path = f"images/02Dic/{img_name}.jpg"
    if not os.path.exists(img_path):
        print(f"File not found: {img_path}")
        return

    img = cv2.imread(img_path)
    
    # Load user params
    with open("src/config_esquinas.json", "r") as f:
        params_esquinas = json.load(f)
    with open("src/config_bolsas.json", "r") as f:
        params_bolsas = json.load(f)

    # Get mask_caja
    mask_caja, _ = obtener_mascara_roi_solida(img, params_esquinas)
    cv2.imwrite(f"debug_{img_name}_mask_caja.jpg", mask_caja)
    
    # Get bag mask (without mask_caja filter first)
    # We'll use a modified call or just look at the code
    # Actually, let's just run detection and print stats
    bolsas, res = detectar_bolsas_cv(image_bgr=img, params=params_bolsas, mask_caja=mask_caja)
    cv2.imwrite(f"debug_{img_name}_result.jpg", res)
    
    print(f"Image: {img_name}")
    print(f"Mask Caja Area: {np.sum(mask_caja > 0)}")
    print(f"Bags found: {len(bolsas)}")

debug_masks("real1")
debug_masks("real3")
debug_masks("real4")
