from __future__ import annotations

import re
import unicodedata
from datetime import datetime

# Conservative aliases: only labels that are semantically equivalent belong together.
ALIASES: dict[str, set[str]] = {
    "full_name": {
        "full name",
        "name",
        "legal name",
        "applicant name",
        "姓名",
        "名字",
    },
    "first_name": {"first name", "given name", "forename", "名"},
    "last_name": {"last name", "surname", "family name", "姓"},
    "email": {
        "email",
        "email address",
        "primary email",
        "primary email address",
        "e mail",
        "电子邮箱",
        "邮箱",
    },
    "phone": {
        "phone",
        "phone number",
        "mobile",
        "mobile number",
        "telephone",
        "联系电话",
        "手机号",
        "电话",
    },
    "date_of_birth": {"date of birth", "birth date", "dob", "出生日期", "生日"},
    "address": {"address", "street address", "home address", "mailing address", "地址"},
    "city": {"city", "town", "城市"},
    "state": {"state", "province", "region", "state province", "省", "州"},
    "postal_code": {"postal code", "zip", "zip code", "postcode", "邮编", "邮政编码"},
    "country": {"country", "country of residence", "nation", "国家", "居住国家"},
    "nationality": {"nationality", "citizenship", "国籍"},
    "organization": {
        "organization",
        "organisation",
        "company",
        "employer",
        "institution",
        "单位",
        "公司",
        "机构",
    },
    "job_title": {"job title", "title", "position", "role", "职位", "职务"},
    "student_id": {"student id", "student number", "学号"},
    "website": {"website", "web site", "homepage", "portfolio", "个人网站"},
    "linkedin": {"linkedin", "linkedin profile"},
    "github": {"github", "github profile", "github username"},
    "degree": {"degree", "qualification", "学历", "学位"},
    "major": {"major", "field of study", "专业"},
    "graduation_date": {"graduation date", "graduated", "毕业日期", "毕业时间"},
    "consent": {"consent", "agree", "agreement", "同意", "确认"},
}


def normalize_label(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    value = re.sub(r"[_./\\-]+", " ", value)
    value = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def canonical_key(label: str) -> str:
    normalized = normalize_label(label)
    for key, aliases in ALIASES.items():
        if normalized == key.replace("_", " ") or normalized in aliases:
            return key
    return normalized.replace(" ", "_")


def normalize_value(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip()
    return re.sub(r"\s+", " ", text).casefold()


def display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return re.sub(r"\s+", " ", str(value).strip())


def looks_like_date_key(key: str) -> bool:
    return key in {"date_of_birth", "graduation_date"} or key.endswith("_date")


def normalize_date(value: str) -> str:
    """Return an ISO date when the input is unambiguous; otherwise preserve it."""
    text = value.strip()
    formats = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%B %d, %Y", "%b %d, %Y")
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return text
