from typing import Any, Dict, Optional

from customer.models import Customer
from settings.LINE import reply_line_text


def _normalize_company_name(name: str) -> str:
    return "".join(str(name or "").lower().split())


# 检查是否已存在此公司
def _find_existing_customer_by_company_name(company_name: str) -> Optional[Customer]:
    normalized_target = _normalize_company_name(company_name)
    if not normalized_target:
        return None
    queryset = Customer.objects.filter(deleted_at__isnull=True).order_by("-created_at", "-id")
    for item in queryset:
        if _normalize_company_name(item.company_name) == normalized_target:
            return item
    return None


# 已存在此公司，查找联系人空位
def _find_first_empty_contact_slot(customer: Customer) -> Optional[int]:
    for slot in (1, 2, 3):
        name = str(getattr(customer, f"contact{slot}_name", "") or "").strip()
        email = str(getattr(customer, f"contact{slot}_email", "") or "").strip()
        phone = str(getattr(customer, f"contact{slot}_phone", "") or "").strip()
        if not name and not email and not phone:
            return slot
    return None


# 将联系人插入到指定位置
def _apply_card_to_contact_slot(customer: Customer, slot: int, result: Dict[str, Any]) -> str:
    phone = str(result.get("mobile") or result.get("tel") or "").strip()
    setattr(customer, f"contact{slot}_name", str(result.get("name") or "").strip())
    setattr(customer, f"contact{slot}_position", str(result.get("title") or "").strip())
    setattr(customer, f"contact{slot}_email", str(result.get("email") or "").strip())
    setattr(customer, f"contact{slot}_phone", phone)
    return (
        "\n"
        f"联系人{slot}姓名:{str(result.get('name') or '').strip()}\n"
        f"联系人{slot}职位:{str(result.get('title') or '').strip()}\n"
        f"联系人{slot}邮箱:{str(result.get('email') or '').strip()}\n"
        f"联系人{slot}电话:{phone}\n"
    )


# 将名片转为customer
def process_uploaded_card_image(image_path: str, reply_token: str) -> Dict[str, Any]:
    from customer.card_ocr import parse_card

    result = parse_card(image_path)
    company_name = str(result.get("company") or "").strip()
    if not company_name:
        reply_line_text(reply_token, "已收到图片，但未识别到公司名，请后台确认。")
        return {
            "status": "missing_company",
            "result": result,
            "message": "未识别到公司名",
        }

    existing = _find_existing_customer_by_company_name(company_name)
    if not existing:
        customer = Customer()
        customer.company_name = company_name
        customer.company_address = str(result.get("address") or "").strip()
        res = _apply_card_to_contact_slot(customer, 1, result)
        customer.created_by = 1
        customer.save()
        reply_line_text(reply_token, f"已收到图片，已新建客户：{company_name}，\n 内容：【{res}】")
        return {
            "status": "created",
            "customer_id": customer.id,
            "company_name": customer.company_name,
            "slot": 1,
            "result": result,
        }

    slot = _find_first_empty_contact_slot(existing)
    if not slot:
        reply_line_text(reply_token, f"已收到图片，但客户【{company_name}】联系人已满，请后台手动处理后，再次上传。")
        return {
            "status": "contacts_full",
            "customer_id": existing.id,
            "company_name": existing.company_name,
            "result": result,
            "message": "公司联系人已满",
        }

    res = _apply_card_to_contact_slot(existing, slot, result)
    existing.updated_by = 1
    existing.save()
    reply_line_text(reply_token, f"已收到图片，已追加到客户【{company_name}】的联系人{slot}，\n 内容：【{res}】")
    return {
        "status": "appended",
        "customer_id": existing.id,
        "company_name": existing.company_name,
        "slot": slot,
        "result": result,
    }
