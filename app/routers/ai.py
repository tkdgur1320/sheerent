# 이건 전후비교 해서 파손감지 됐는지 확인하는 코드(라우터로 바꿨는데 테스트 못함, yolov5폴더에 compare.py가 원본)

from fastapi import APIRouter, UploadFile, File
import os
from datetime import datetime
from collections import defaultdict
import torch
from PIL import Image
import io

router = APIRouter()

# YOLOv5 모델 경로
weights_path = r"C:\Users\user\Desktop\yolov5\yolov5\runs\train\my_yolo_model\weights\best.pt"

# YOLOv5 모델 로드
model = torch.load(weights_path, map_location='cuda')['model'].float().fuse().eval()

# 클래스 이름 리스트 (data.yaml 기준 순서!)
class_names = ['crack', 'scratch']

def generate_rental_id(item_id, user_id):
    date_str = datetime.now().strftime('%Y%m%d')
    return f"{item_id}_{user_id}_{date_str}"

def run_yolo_with_system(image_path, rental_id, folder_name):
    output_dir = f"results/{rental_id}/{folder_name}"
    os.makedirs(output_dir, exist_ok=True)

    # detect.py 실행
    command = (
        f"python yolov5/detect.py "
        f"--weights \"{weights_path}\" "
        f"--source \"{image_path}\" "
        f"--conf 0.5 "
        f"--project results/{rental_id} "
        f"--name {folder_name} "
        f"--exist-ok "
        f"--save-txt"
    )
    os.system(command)

    label_txt_dir = f"results/{rental_id}/{folder_name}/labels"
    class_counts = defaultdict(int)

    if not os.path.exists(label_txt_dir):
        return {}

    for label_file in os.listdir(label_txt_dir):
        file_path = os.path.join(label_txt_dir, label_file)
        with open(file_path, 'r') as f:
            for line in f:
                cls_id = int(line.split()[0])  # 첫 번째 값은 클래스 ID
                class_name = class_names[cls_id] if cls_id < len(class_names) else f"class_{cls_id}"
                class_counts[class_name] += 1

    return dict(class_counts)

def is_item_damaged(item_id, user_id, before_img, after_img):
    rental_id = generate_rental_id(item_id, user_id)

    before_counts = run_yolo_with_system(before_img, rental_id, '등록')
    after_counts = run_yolo_with_system(after_img, rental_id, '반납')

    damage_detected = False
    increased_classes = {}

    all_classes = set(before_counts.keys()).union(set(after_counts.keys()))

    for cls in all_classes:
        before = before_counts.get(cls, 0)
        after = after_counts.get(cls, 0)
        if after > before:
            damage_detected = True
            increased_classes[cls] = after - before

    return rental_id, damage_detected, increased_classes

@router.post("/check_damage/")
async def check_damage(item_id: str, user_id: str, before_file: UploadFile = File(...), after_file: UploadFile = File(...)):
    # 업로드된 이미지 파일 처리
    before_img = before_file.filename
    after_img = after_file.filename

    before_file_path = f"temp/{before_img}"
    after_file_path = f"temp/{after_img}"

    with open(before_file_path, "wb") as f:
        f.write(await before_file.read())
    
    with open(after_file_path, "wb") as f:
        f.write(await after_file.read())

    # 파손 판단
    rental_id, damaged, damage_info = is_item_damaged(item_id, user_id, before_file_path, after_file_path)

    # 임시 파일 삭제
    os.remove(before_file_path)
    os.remove(after_file_path)

    if damaged:
        return {"rental_id": rental_id, "damage_detected": True, "damage_info": damage_info}
    else:
        return {"rental_id": rental_id, "damage_detected": False}
