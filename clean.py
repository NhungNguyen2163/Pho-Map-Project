import pandas as pd
import re

# ---- Load CSV ----
file_path = r"C:\Users\Nhung\Downloads\We_Love_Pho\Raw data\consolidated_2025-05-24_22-33-52.csv"
df = pd.read_csv(file_path)

# ---- Lọc chỉ giữ dòng có "Sweden" trong address ----
df = df[df["address"].str.contains("Sweden", case=False, na=False)].copy()

# ---- Clean số điện thoại ----
def clean_phone(phone):
    if pd.isna(phone):
        return ""
    phone = re.sub(r"[^\d+]", "", str(phone))
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if not phone.startswith("+") and phone.startswith("0"):
        phone = "+46" + phone[1:]
    return phone

df["phone"] = df["phone"].apply(clean_phone)

# ---- Chuẩn hóa URL ----
def normalize_url(url):
    if pd.isna(url) or not isinstance(url, str) or url.strip() == "":
        return ""
    if not url.startswith("http"):
        return "http://" + url.strip()
    return url.strip()

for col in ["website", "facebook", "instagram", "x_twitter", "menu_url"]:
    df[col] = df[col].apply(normalize_url)

# ---- Làm sạch mô tả ----
def clean_description(desc):
    if pd.isna(desc):
        return ""
    desc = re.sub(r"<[^>]+>", "", desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc[:300] + "..." if len(desc) > 300 else desc

df["description"] = df["description"].apply(clean_description)

# ---- Gắn cờ thiếu thông tin ----
df["missing_website"] = df["website"].apply(lambda x: x == "")
df["missing_phone"] = df["phone"].apply(lambda x: x == "")
df["missing_description"] = df["description"].apply(lambda x: x == "")
df["missing_social"] = df[["facebook", "instagram", "x_twitter"]].apply(lambda x: all(val == "" for val in x), axis=1)

# ---- Xuất file kết quả ----
output_path = r"C:\Users\Nhung\Downloads\We_Love_Pho\Raw data\consolidated_cleaned_final.csv"
df.to_csv(output_path, index=False)

# ---- Xem trước kết quả ----
print("✅ Cleaned data saved to:", output_path)
print(df.head(5))
