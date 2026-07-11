"""Travel (小象旅行) routes: integration, postcard, history."""
import os
import io
import json
import time
import uuid
import random
import base64

from fastapi import APIRouter, HTTPException
from PIL import Image, ImageOps, ImageDraw

from api.state import get_db, get_store, get_model_client
from api.models import PostcardFinalizeRequest
from core.generator import GeminiGenerator

router = APIRouter(tags=["travel"])


@router.post("/travel/integrate")
async def generate_travel_integrate():
    try:
        db = get_db()
        store = get_store()

        # Pure random selection with rejection sampling
        # P1a stage 2: sample candidates in SQL instead of loading all.
        store = get_store()
        if store.count_photos() > 0:
            all_files = store.get_random_photos(200)
        else:
            all_files = db.get_all_files_with_time()
        if not all_files:
            raise Exception("Database is empty.")

        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'}
        random.shuffle(all_files)

        target_photo = None
        for f in all_files:
            f_path = f.get('file_path', '')
            f_tag = str(f.get('tag', '')).lower()
            if f_tag in ['document', 'screenshot', 'trash', 'memo', 'card', 'text']:
                continue
            if os.path.splitext(f_path)[1].lower() in video_extensions:
                continue
            if not os.path.exists(f_path):
                continue

            try:
                with Image.open(f_path) as img:
                    w, h = img.size
                    ratio = w / h
                    if ratio < 0.45 or ratio > 2.2:
                        continue
                    if w < 400 or h < 400:
                        continue
            except Exception:
                continue

            target_photo = f
            break

        if not target_photo:
            raise Exception("No suitable photos found.")

        candidates = [target_photo]
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                target_photo = random.choice(candidates)
                original_pil = Image.open(target_photo['file_path']).convert('RGB')
                original_pil = ImageOps.exif_transpose(original_pil)

                max_dim = 2048
                if max(original_pil.size) > max_dim:
                    original_pil.thumbnail((max_dim, max_dim), Image.LANCZOS)

                w, h = original_pil.size
                def round64(x): return (x // 64) * 64
                fw, fh = round64(w), round64(h)
                if fw != w or fh != h:
                    original_pil = original_pil.resize((fw, fh), Image.LANCZOS)
                    w, h = fw, fh

                # Planner
                planner = get_model_client("travel_prompt", store)
                time_str = "Unknown Day"
                photo_ts = target_photo.get('captured_time', 0)
                if photo_ts > 0:
                    time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(photo_ts))
                location = target_photo.get('location_info', {})
                loc_str = location.get('city', "") or location.get('province', "") or "陕西西安"

                vqa_prompt = (
                    f"You are a photo editor. Object: A cute cartoon Elephant.\n"
                    f"Task: Analyze the photo and find the BEST position to place the elephant.\n"
                    f"Context: {w}x{h}. Location: {loc_str}. Time: {time_str}.\n"
                    f"Output JSON: 'elephant_position', 'action', 'outfit', 'scene_desc'.\n"
                    f"DO NOT describe postmarks or frames."
                )

                plan = {}
                try:
                    plan_resp = planner.generate(vqa_prompt, reference_images=[original_pil])
                    if isinstance(plan_resp, tuple):
                        _, plan_text = plan_resp
                    else:
                        plan_text = str(plan_resp)
                    json_str = plan_text
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0].strip()
                    plan = json.loads(json_str)
                except Exception:
                    plan = {}

                # Generate Mask
                mask_img = Image.new('L', (w, h), 0)
                draw_mask = ImageDraw.Draw(mask_img)
                pos_str = plan.get("elephant_position", "bottom-right").lower()
                ele_size = min(w, h) // 3
                ex, ey = w // 2, h // 2
                if "left" in pos_str: ex = ele_size // 2 + 20
                if "right" in pos_str: ex = w - ele_size // 2 - 20
                if "top" in pos_str: ey = ele_size // 2 + 20
                if "bottom" in pos_str: ey = h - ele_size // 2 - 20
                e_box = (max(0, ex - ele_size // 2), max(0, ey - ele_size // 2),
                         min(w, ex + ele_size // 2), min(h, ey + ele_size // 2))
                draw_mask.rectangle(e_box, fill=255)

                # Reference Elephant
                assets_dir = store.get_config("assets_dir", "./assets")
                ref_path = os.path.join(assets_dir, "elephant_reference.png")
                ref_imgs = [original_pil]
                if os.path.exists(ref_path):
                    r = Image.open(ref_path)
                    r.thumbnail((512, 512))
                    ref_imgs.append(r)

                # Generate Integration
                gen = get_model_client("travel_integrate", store)
                action = plan.get("action", "standing happy")
                outfit = plan.get("outfit", "casual clothes")
                pos = plan.get("elephant_position", "in the scene")
                final_prompt = (f"High quality travel photo. A cute cartoon elephant wearing {outfit} "
                                f"is {action} at {pos}. The background MUST be exactly the same as the original photo.")

                if isinstance(gen, GeminiGenerator):
                    res_img, _ = gen.generate(final_prompt, reference_images=ref_imgs, mask_image=mask_img, width=fw, height=fh)
                else:
                    res_img = gen.generate(final_prompt, reference_images=ref_imgs, mask_image=mask_img, width=fw, height=fh)

                if isinstance(res_img, str):
                    raise Exception("Generator returned text.")
                if res_img.mode != 'RGB':
                    res_img = res_img.convert('RGB')

                cache_dir = os.path.join(assets_dir, "cache_integrated")
                os.makedirs(cache_dir, exist_ok=True)
                filename = f"integrated_{uuid.uuid4().hex}.png"
                save_path = os.path.join(cache_dir, filename)
                res_img.save(save_path)

                return {
                    "status": "success", "integrated_path": save_path,
                    "original_path": target_photo['file_path'],
                    "scene": plan.get("scene_desc", "Travel Scene"),
                    "outfit": plan.get("outfit", "Casual"),
                    "preview_url": f"/files/content?path={save_path}"
                }

            except Exception as e:
                last_error = e
                err_msg = str(e)
                if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise HTTPException(429, "External API Quota Exhausted.")
                elif "PROHIBITED" in err_msg or "blocked" in err_msg.lower():
                    continue
                else:
                    raise

        raise HTTPException(500, f"Failed after retries. Last: {last_error}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))


@router.post("/travel/postcard_finalize")
async def generate_travel_finalize(req: PostcardFinalizeRequest):
    try:
        store = get_store()
        if not os.path.exists(req.integrated_path):
            raise HTTPException(400, "Integrated image not found")

        user_img = Image.open(req.integrated_path).convert('RGB')
        w, h = user_img.size

        # Planner
        planner = get_model_client("travel_prompt", store)
        vqa_prompt = (
            f"You are a high-fashion postcard designer.\n"
            f"Context: {w}x{h}. Photo has a cute elephant.\n"
            f"Task: Design a STYLISH, PREMIUM layout.\n"
            f"Output JSON: 'layout_config' (type, bg_color, ratio, text_color, font_style), "
            f"'message' (Chinese), 'location_name' (Chinese), 'date_str' (YYYY.MM.DD)"
        )

        try:
            plan_resp = planner.generate(vqa_prompt, reference_images=[user_img])
            if isinstance(plan_resp, tuple):
                _, plan_text = plan_resp
            else:
                plan_text = str(plan_resp)
            json_str = plan_text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            plan = json.loads(json_str)
        except Exception:
            plan = {
                "layout_config": {"type": random.choice(["polaroid", "magazine", "film"]), "ratio": 0.2, "bg_color": "#F5F5DC"},
                "message": "美好的一天！", "location_name": "陕西西安"
            }

        # Canvas expansion
        scale_factor = 1.8
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        max_dim = 1280
        if new_w > max_dim or new_h > max_dim:
            ratio = min(max_dim / new_w, max_dim / new_h)
            new_w = int(new_w * ratio)
            new_h = int(new_h * ratio)

        extended_img = Image.new('RGB', (new_w, new_h), (255, 255, 255))
        paste_x = (new_w - w) // 2
        paste_y = (new_h - h) // 2
        extended_img.paste(user_img, (paste_x, paste_y))

        gen = get_model_client("travel_postcard", store)
        loc_name = plan.get("location_name", "陕西西安")
        date_str = plan.get("date_str", time.strftime("%Y.%m.%d"))
        message = plan.get("message", f"我在{loc_name}！")

        design_styles = [
            "Kawaii Japanese Journal Style, pastel colors, cute stickers",
            "Korean Polco Style, sparkly stickers, soft aesthetic",
            "Whimsical Scrapbook Layout, cute animal illustrations",
            "High-End Fashion Brand Lookbook, sophisticated layout",
            "Minimalist Kinfolk Magazine Style, elegant serif typography",
        ]
        style_prompt = random.choice(design_styles)

        final_prompt = (
            f"Role: Expert Graphic Designer. Task: Create a Minimalist Postcard.\n"
            f"Style: {style_prompt}.\n"
            f"DESIGN RULES: Keep CLEAN layout. Write message in handwritten font.\n"
            f"Message: '亲爱的朋友，{message} 来自小象 🐘'\n"
            f"STAMPS: Draw a postage stamp with illustration matching the photo content.\n"
            f"POSTMARK: '{loc_name} {date_str}'\n"
            f"PRESERVE the central photo."
        )

        try:
            if isinstance(gen, GeminiGenerator):
                res_img, _ = gen.generate(final_prompt, reference_images=[extended_img], width=new_w, height=new_h)
            else:
                res_img = gen.generate(final_prompt, reference_images=[extended_img], width=new_w, height=new_h)
        except Exception:
            res_img = extended_img

        if isinstance(res_img, str):
            raise Exception("Generator returned text.")
        res_img = res_img.convert('RGB')

        assets_dir = store.get_config("assets_dir", "./assets")
        cards_dir = os.path.join(assets_dir, "user_postcards")
        os.makedirs(cards_dir, exist_ok=True)
        ts_str = time.strftime("%Y%m%d_%H%M%S")
        filename = f"postcard_{ts_str}_{uuid.uuid4().hex[:6]}.jpg"
        save_path = os.path.join(cards_dir, filename)
        res_img.save(save_path, format="JPEG", quality=95)

        metadata = {
            "original_file_path": req.original_path, "message": message,
            "scene": req.scene, "outfit": req.outfit, "timestamp": ts_str
        }
        meta_path = save_path.replace('.jpg', '.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        buffered = io.BytesIO()
        res_img.save(buffered, format="JPEG", quality=90)
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return {"status": "success", "image": "data:image/jpeg;base64," + img_str, "saved_path": save_path}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))


@router.get("/travel/history")
def get_postcard_history():
    try:
        store = get_store()
        assets_dir = store.get_config("assets_dir", "./assets")
        cards_dir = os.path.join(assets_dir, "user_postcards")
        if not os.path.exists(cards_dir):
            return []

        files = []
        for f in os.listdir(cards_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = os.path.join(cards_dir, f)
                files.append({"filename": f, "path": full_path, "time": os.path.getmtime(full_path)})
        files.sort(key=lambda x: x["time"], reverse=True)
        return files
    except Exception:
        return []


@router.delete("/travel/postcards")
def delete_all_postcards():
    try:
        store = get_store()
        assets_dir = store.get_config("assets_dir", "./assets")
        cards_dir = os.path.join(assets_dir, "user_postcards")
        count = 0
        if os.path.exists(cards_dir):
            for f in os.listdir(cards_dir):
                file_path = os.path.join(cards_dir, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
        return {"status": "success", "deleted_count": count}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/travel/postcard/{filename}")
def delete_postcard(filename: str):
    try:
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(400, "Invalid filename")
        store = get_store()
        assets_dir = store.get_config("assets_dir", "./assets")
        target_path = os.path.join(assets_dir, "user_postcards", filename)
        if os.path.exists(target_path):
            os.remove(target_path)
            return {"status": "deleted"}
        raise HTTPException(404, "File not found")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/travel/postcard/{filename}/metadata")
def get_postcard_metadata(filename: str):
    try:
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(400, "Invalid filename")
        store = get_store()
        assets_dir = store.get_config("assets_dir", "./assets")
        metadata_filename = filename.replace('.jpg', '.json').replace('.jpeg', '.json').replace('.png', '.json')
        metadata_path = os.path.join(assets_dir, "user_postcards", metadata_filename)
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise HTTPException(404, "Metadata not found")
    except Exception as e:
        raise HTTPException(500, str(e))
