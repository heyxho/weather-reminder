import sys
import requests
import json
from datetime import datetime, timedelta

# 强制刷新输出，确保日志可见
def debug_print(msg):
    print(msg, flush=True)
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

# ==================== 配置区 ====================
WEWORK_WEBHOOK = "这里替换为你的群机器人Webhook地址"

LATITUDE = 36.389
LONGITUDE = 120.447
CITY_NAME = "青岛即墨"

LAST_ALERT_DATE = {"today": "", "tomorrow": ""}
# ===============================================

def get_weather_forecast():
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=weathercode&daily=weathercode&timezone=Asia/Shanghai&forecast_days=3"
    try:
        response = requests.get(weather_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        debug_print(f"获取天气数据失败: {e}")
        return None

def is_rain(weathercode):
    rain_codes = set(range(51, 58)) | set(range(61, 68)) | set(range(80, 83)) | {95, 96, 99}
    return weathercode in rain_codes

def send_wework_message(content):
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "text",
        "text": {"content": content}
    }
    try:
        resp = requests.post(WEWORK_WEBHOOK, json=payload, headers=headers)
        debug_print(f"消息发送结果: {resp.text}")
    except Exception as e:
        debug_print(f"消息发送失败: {e}")

def check_and_notify():
    debug_print("========== 调试信息开始 ==========")
    weather_data = get_weather_forecast()
    if not weather_data:
        debug_print("无法获取天气数据")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    daily_data = weather_data.get("daily", {})
    daily_weathercodes = daily_data.get("weathercode", [])
    daily_times = daily_data.get("time", [])
    
    debug_print(f"今天的日期: {today_str}")
    debug_print(f"明天的日期: {tomorrow_str}")
    debug_print(f"API返回的每日时间列表: {daily_times}")
    debug_print(f"API返回的每日天气代码列表: {daily_weathercodes}")
    
    for i, day_str in enumerate(daily_times):
        if i >= len(daily_weathercodes):
            break
        code = daily_weathercodes[i]
        rain_flag = is_rain(code)
        debug_print(f"日期 {day_str} -> 天气代码 {code} -> 是否有雨: {rain_flag}")
    
    debug_print("========== 调试信息结束 ==========")
    
    # 以下为原有的发送逻辑
    today_has_rain = False
    for i, day_str in enumerate(daily_times):
        if day_str == today_str and i < len(daily_weathercodes):
            if is_rain(daily_weathercodes[i]):
                today_has_rain = True
            break
    
    tomorrow_has_rain = False
    for i, day_str in enumerate(daily_times):
        if day_str == tomorrow_str and i < len(daily_weathercodes):
            if is_rain(daily_weathercodes[i]):
                tomorrow_has_rain = True
            break
    
    if today_has_rain and LAST_ALERT_DATE.get("today") != today_str:
        msg = f"🌧️ {CITY_NAME}今天整体预报有雨，请及时将室外货物移至室内！"
        send_wework_message(msg)
        LAST_ALERT_DATE["today"] = today_str
    else:
        debug_print("今天无雨或已提醒过，不发送今日提醒")
    
    if tomorrow_has_rain and LAST_ALERT_DATE.get("tomorrow") != tomorrow_str:
        msg = f"🌙 {CITY_NAME}明天预报有雨，请在下班前将室外货物移至室内！"
        send_wework_message(msg)
        LAST_ALERT_DATE["tomorrow"] = tomorrow_str
    else:
        debug_print("明天无雨或已提醒过，不发送明日提醒")

if __name__ == "__main__":
    check_and_notify()
