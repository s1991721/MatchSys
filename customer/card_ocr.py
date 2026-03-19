from typing import List, Optional


def _deduplicate(items: List[str]) -> List[str]:
    result = []
    seen = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _extract_email(text: str) -> Optional[str]:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else None


def _extract_website(text: str) -> Optional[str]:
    candidates = re.findall(
        r"(https?://[^\s]+|www\.[^\s]+|[A-Za-z0-9.-]+\.(?:com|jp|co\.jp|net|org|io|biz|info))",
        text,
        flags=re.IGNORECASE
    )
    for c in candidates:
        c = c.strip().rstrip(".,;")
        if "@" not in c and "." in c:
            return c
    return None


def _extract_phone_numbers(text: str) -> List[str]:
    """
    尽量兼容日本号码格式：
    - 03-1234-5678
    - 090-1234-5678
    - +81-3-1234-5678
    - 075-123-4567
    """
    patterns = [
        r"(?:\+81[-\s]?)?(?:0\d{1,4})[-\s]?\d{1,4}[-\s]?\d{3,4}",
        r"(?:\+?\d{1,3}[-\s]?)?(?:\(?\d{1,4}\)?[-\s]?)?\d{1,4}[-\s]?\d{2,4}[-\s]?\d{3,4}",
    ]

    phones = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            value = "".join(m) if isinstance(m, tuple) else m
            value = re.sub(r"\s+", "", value)
            digits = re.sub(r"\D", "", value)
            if 9 <= len(digits) <= 13:
                phones.append(value)

    return _deduplicate(phones)


import re
from typing import List, Optional, Dict
import os


class _BusinessCardParser:
    def __init__(self):
        # 日语职位关键词
        self.title_keywords = [
            "代表取締役", "取締役", "社長", "副社長",
            "部長", "課長", "係長", "主任",
            "営業部長", "営業課長", "マネージャー",
            "エンジニア", "営業", "担当",
            "CEO", "CTO", "COO", "CFO",
            "Manager", "Director", "Engineer", "Consultant"
        ]

        # 日语公司关键词
        self.company_keywords = [
            "株式会社", "有限会社", "合同会社", "会社",
            "研究所", "研究院", "センター",
            "Inc", "Ltd", "LLC", "Corp", "Company", "Co."
        ]

        # 日语地址关键词
        self.address_keywords = [
            "住所", "〒", "都", "道", "府", "県", "市", "区",
            "町", "村", "丁目", "番地", "号", "ビル", "階",
            "Address", "Road", "Rd", "Street", "St.", "Ave", "Avenue", "Building"
        ]

        # 联系方式关键词
        self.contact_keywords = [
            "tel", "fax", "mobile", "phone", "mail", "e-mail",
            "メール", "携帯", "電話", "直通", "内線",
            "@", "www", "http"
        ]

        # 不太可能是姓名的关键词
        self.name_blacklist = [
            "株式会社", "有限会社", "合同会社", "会社",
            "tel", "fax", "mobile", "phone", "mail", "e-mail",
            "メール", "携帯", "電話", "住所", "〒",
            "@", "www", "http",
            "代表取締役", "取締役", "社長", "副社長",
            "部長", "課長", "係長", "主任",
            "manager", "director", "engineer", "consultant", "ceo", "cto", "coo", "cfo"
        ]

    def normalize_line(self, line: str) -> str:
        line = line.replace("\u3000", " ")
        line = line.strip()
        line = re.sub(r"\s+", " ", line)
        return line

    def is_contact_line(self, line: str) -> bool:
        low = line.lower()
        return any(k in low for k in self.contact_keywords)

    def is_company_line(self, line: str) -> bool:
        low = line.lower()
        return any(k.lower() in low for k in self.company_keywords)

    def is_title_line(self, line: str) -> bool:
        low = line.lower()
        return any(k.lower() in low for k in self.title_keywords)

    def is_address_line(self, line: str) -> bool:
        low = line.lower()
        return any(k.lower() in low for k in self.address_keywords)

    def is_possible_japanese_name(self, line: str) -> bool:
        """
        判断是否可能是日语/中文姓名：
        支持：
        - 山田太郎
        - 山田 太郎
        - ヤマダ タロウ
        - やまだ たろう
        """
        line = self.normalize_line(line)

        # 太长通常不是姓名
        if len(line) < 2 or len(line) > 20:
            return False

        # 含数字通常不是姓名
        if re.search(r"\d", line):
            return False

        # 包含明显分隔符通常不是姓名
        if any(x in line for x in ["@", "〒", ":", "：", "/", "http", "www"]):
            return False

        # 纯日文姓名（汉字 / 平假名 / 片假名，可带一个空格）
        # patterns = [
        #     r"^[一-龥]{2,8}$",
        #     r"^[一-龥]{1,4}\s[一-龥]{1,4}$",
        #     r"^[ァ-ヴー]{2,20}$",
        #     r"^[ァ-ヴー]{1,10}\s[ァ-ヴー]{1,10}$",
        #     r"^[ぁ-んー]{2,20}$",
        #     r"^[ぁ-んー]{1,10}\s[ぁ-んー]{1,10}$",
        #     r"^[一-龥ァ-ヴーぁ-ん]{2,20}$",
        #     r"^[一-龥ァ-ヴーぁ-ん]{1,10}\s[一-龥ァ-ヴーぁ-ん]{1,10}$",
        # ]

        japanese_patterns = [
            r"^[\u4E00-\u9FFF]{2,8}$",
            r"^[\u4E00-\u9FFF]{1,4}\s[\u4E00-\u9FFF]{1,4}$",
            r"^[\u30A0-\u30FFー]{2,20}$",
            r"^[\u30A0-\u30FFー]{1,10}\s[\u30A0-\u30FFー]{1,10}$",
            r"^[\u3040-\u309Fー]{2,20}$",
            r"^[\u3040-\u309Fー]{1,10}\s[\u3040-\u309Fー]{1,10}$",
            r"^[\u4E00-\u9FFF\u30A0-\u30FF\u3040-\u309Fー]{2,20}$",
            r"^[\u4E00-\u9FFF\u30A0-\u30FF\u3040-\u309Fー]{1,10}\s[\u4E00-\u9FFF\u30A0-\u30FF\u3040-\u309Fー]{1,10}$",
        ]

        # 扩展 CJK 范围，兼容部分繁体/生僻字
        han = r"[\u3400-\u4DBF\u4E00-\u9FFF]"

        # 中文姓名（常见 2-4 字、复姓、空格分隔、少数民族中间点）
        chinese_patterns = [
            rf"^{han}{{2,4}}$",
            rf"^{han}{{1,2}}\s{han}{{1,3}}$",
            rf"^{han}{{1,4}}\s*[·・•]\s*{han}{{1,8}}$",
            rf"^{han}{{1,4}}\s*[·・•]\s*{han}{{1,8}}\s*[·・•]\s*{han}{{1,8}}$",
        ]

        return (
            any(re.fullmatch(p, line) for p in japanese_patterns)
            or any(re.fullmatch(p, line) for p in chinese_patterns)
        )

    def is_possible_english_name(self, line: str) -> bool:
        line = self.normalize_line(line)

        if len(line) < 2 or len(line) > 30:
            return False

        if re.search(r"\d", line):
            return False

        return bool(re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+){0,3}", line))

    def guess_name(self, lines: List[str]) -> Optional[str]:
        """
        姓名通常出现在名片上半部分，所以优先扫描前几行。
        这里不再写死 [:5]，而是动态限制扫描范围。
        """
        max_scan_lines = min(len(lines), 8)

        for i in range(max_scan_lines):
            line = self.normalize_line(lines[i])
            low = line.lower()

            if not line:
                continue

            if any(k.lower() in low for k in self.name_blacklist):
                continue

            if self.is_contact_line(line):
                continue

            if self.is_company_line(line):
                continue

            if self.is_address_line(line):
                continue

            if self.is_possible_japanese_name(line):
                return line

            # if self.is_possible_english_name(line):
            #     return line

        return None

    def guess_title(self, lines: List[str]) -> Optional[str]:
        """
        职位可能出现在姓名前后，通常也在名片上半部分。
        """
        max_scan_lines = min(len(lines), 10)

        for i in range(max_scan_lines):
            line = self.normalize_line(lines[i])
            if self.is_title_line(line):
                return line

        return None

    def guess_company(self, lines: List[str]) -> Optional[str]:
        """
        公司名通常在顶部区域。
        """
        max_scan_lines = min(len(lines), 8)

        for i in range(max_scan_lines):
            line = self.normalize_line(lines[i])
            if self.is_company_line(line):
                return line

        # 如果没命中关键词，从前几行里挑一个最像公司名的
        candidates = []
        for i in range(max_scan_lines):
            line = self.normalize_line(lines[i])
            low = line.lower()

            if not line:
                continue

            if self.is_contact_line(line):
                continue

            if "@" in line or "www" in low or "http" in low:
                continue

            # 姓名一般较短，公司名一般相对长一些
            if len(line) >= 5:
                candidates.append(line)

        if candidates:
            return max(candidates, key=len)

        return None

    def guess_address(self, lines: List[str]) -> Optional[str]:
        """
        地址通常在名片下半部分，但也可能分多行。
        这里把所有疑似地址行收集起来，再合并。
        """
        candidates = []

        for line in lines:
            line = self.normalize_line(line)
            if not line:
                continue

            if self.is_address_line(line):
                candidates.append(line)
                continue

            # 日本地址常含数字 + 地名/丁目/番地
            if re.search(r"\d", line) and any(
                    k in line for k in ["都", "道", "府", "県", "市", "区", "町", "丁目", "番地", "号"]):
                candidates.append(line)

        if candidates:
            # 去重并合并
            unique_candidates = []
            for c in candidates:
                if c not in unique_candidates:
                    unique_candidates.append(c)
            return " ".join(unique_candidates)

        return None

    def extract_phone_details(self, lines: List[str], merged_text: str) -> Dict[str, Optional[str]]:
        """
        识别并区分：
        - tel
        - fax
        - mobile
        """
        result = {
            "tel": None,
            "fax": None,
            "mobile": None,
            "phones": []
        }

        # 先从全文里提取所有号码
        all_phones = _extract_phone_numbers(merged_text)
        result["phones"] = all_phones

        # 再按行判断类型
        phone_pattern = r"(?:\+?\d{1,3}[-\s]?)?(?:\(?\d{1,4}\)?[-\s]?)?\d{1,4}[-\s]?\d{2,4}[-\s]?\d{3,4}"

        for line in lines:
            raw_line = self.normalize_line(line)
            low = raw_line.lower()

            matches = re.findall(phone_pattern, raw_line)
            if not matches:
                continue

            number = matches[0].strip()

            if ("fax" in low or "ｆａｘ" in raw_line) and result["fax"] is None:
                result["fax"] = number
            elif any(k in low for k in ["mobile", "携帯", "cell"]) and result["mobile"] is None:
                result["mobile"] = number
            elif any(k in low for k in ["tel", "phone", "電話", "直通"]) and result["tel"] is None:
                result["tel"] = number

        # 如果没有明确 tel，但有 phones，就拿第一个作为 tel
        if result["tel"] is None and result["phones"]:
            result["tel"] = result["phones"][0]

        return result

    def parse(self, lines: List[str]) -> dict:
        # 先做基础清洗
        cleaned_lines = [self.normalize_line(x) for x in lines if self.normalize_line(x)]
        merged_text = "\n".join(cleaned_lines)

        phone_info = self.extract_phone_details(cleaned_lines, merged_text)

        result = {
            "name": self.guess_name(cleaned_lines),
            "company": self.guess_company(cleaned_lines),
            "title": self.guess_title(cleaned_lines),
            "tel": phone_info["tel"],
            "fax": phone_info["fax"],
            "mobile": phone_info["mobile"],
            "phones": phone_info["phones"],
            "email": _extract_email(merged_text),
            "website": _extract_website(merged_text),
            "address": self.guess_address(cleaned_lines),
            "raw_lines": cleaned_lines
        }

        return result


from typing import List
from google.cloud import vision
import json
from pathlib import Path


def _ensure_google_credentials_hardcoded() -> None:
    project_root = Path(__file__).resolve().parent.parent
    credential_path = (project_root / "credentials" / "ocr_credentials.json").resolve()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credential_path)


class _GoogleVisionOCR:
    def __init__(self):
        _ensure_google_credentials_hardcoded()
        cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred:
            raise RuntimeError(
                "Missing GOOGLE_APPLICATION_CREDENTIALS. "
                "Please check OCR settings config."
            )
        if not Path(cred).expanduser().exists():
            raise FileNotFoundError(f"Credential file not found: {cred}")
        self.client = vision.ImageAnnotatorClient()

    def detect_text_lines(self, image_path: str) -> List[str]:
        with open(image_path, "rb") as f:
            content = f.read()

        image = vision.Image(content=content)

        response = self.client.document_text_detection(image=image)

        if response.error.message:
            raise RuntimeError(f"Google Vision OCR failed: {response.error.message}")

        full_text = ""
        if response.full_text_annotation:
            full_text = response.full_text_annotation.text or ""

        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        return lines


def parse_card(file_path: str) -> dict:
    ocr = _GoogleVisionOCR()
    parser = _BusinessCardParser()
    lines = ocr.detect_text_lines(file_path)
    result = parser.parse(lines)
    return result


def main() -> None:
    image_path = Path("/Users/jef/Desktop/card.jpg").expanduser()
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    result = parse_card(str(image_path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
