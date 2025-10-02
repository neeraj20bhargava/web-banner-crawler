from appium import webdriver
from appium.options.android import UiAutomator2Options
import xml.etree.ElementTree as ET
import json

# ------------------------------
# Step 1: Desired Capabilities
# ------------------------------
options = UiAutomator2Options()
options.platform_name = "Android"
options.platform_version = "15.0"
options.device_name = "UGFAJBJZY595D6JZ"  # Replace with your device UDID
options.app_package = "com.careem.acma"
options.app_activity = "com.careem.superapp.core.onboarding.activity.OnboardingActivity"
options.no_reset = True
options.automation_name = "UiAutomator2"

# ------------------------------
# Step 2: Start Appium Session
# ------------------------------
driver = webdriver.Remote("http://127.0.0.1:4723", options=options)

# ------------------------------
# Step 3: Get UI XML Hierarchy
# ------------------------------
page_source = driver.page_source

# ------------------------------
# Step 4: Parse XML
# ------------------------------
root = ET.fromstring(page_source)


def find_banners(node, banners_list):
    """Recursively search for banner elements."""
    resource_id = node.attrib.get("resource-id", "")

    # Target the main carousel container first
    if resource_id == "ea-discovery-home-tiles-carousel-singlerow-fourcolumn":
        # All children of this container are banners
        for child in node:
            banner_info = {
                "text": "",
                "content-desc": child.attrib.get("content-desc", ""),
                "resource-id": child.attrib.get("resource-id", ""),
                "clickable": child.attrib.get("clickable", ""),
                "bounds": child.attrib.get("bounds", "")
            }
            # Look for TextView children for text
            texts = child.findall(".//android.widget.TextView")
            banner_info["text"] = [t.attrib.get("text", "") for t in texts if t.attrib.get("text", "").strip()]
            banners_list.append(banner_info)
    else:
        # Continue searching recursively
        for child in node:
            find_banners(child, banners_list)


# ------------------------------
# Step 5: Extract Banners
# ------------------------------
banners_list = []
find_banners(root, banners_list)

# ------------------------------
# Step 6: Save to JSON
# ------------------------------
with open("careem_banners.json", "w", encoding="utf-8") as f:
    json.dump(banners_list, f, indent=2, ensure_ascii=False)

print("✅ Banner details saved to careem_banners.json")
for b in banners_list:
    print(b)

# ------------------------------
# Step 7: Quit Driver
# ------------------------------
driver.quit()
