import requests
import json
from datetime import datetime, timedelta
import time

# ==================== 配置区 ====================
# 请将第一步获得的Webhook地址填入下面的引号内
WEWORK_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fa2dde06-bf5e-499c-9aaa-548eb085cb24"

# 城市坐标：青岛即墨 (东经120.447, 北纬36.389)[reference:4]
LATITUDE = 36.389
LONGITUDE = 120.447
CITY_NAME = "青岛即墨"

# 为了避免重复发送相同的提醒，可以开启简单记录
LAST_ALERT_DATE = {"today": "", "tomorrow": ""}
# ===============================================

def get_weather_forecast():
    """从Open-Meteo获取未来几天的天气预报"""
    # 请求未来3天的每日天气预报和逐小时天气预报
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=weathercode&daily=weathercode&timezone=Asia/Shanghai&forecast_days=3"
    try:
        response = requests.get(weather_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"获取天气数据失败: {e}")
        return None

def is_rain(weathercode):
    """
    根据Open-Meteo官方WMO气象代码判断是否下雨[reference:5]
    包含毛毛雨(51-57)、雨(61-67)、阵雨(80-82)和雷暴(95/96/99)
    """
    rain_codes = set(range(51, 58)) | set(range(61, 68)) | set(range(80, 83)) | {95, 96, 99}
    return weathercode in rain_codes

def send_wework_message(content):
    """通过Webhook发送消息到企业微信群"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "text",
        "text": {
            "content": content,
            # "mentioned_list": ["@all"]  # 如需@所有人，请取消这行的注释
        }
    }
    try:
        resp = requests.post(WEWORK_WEBHOOK, json=payload, headers=headers)
        print(f"消息发送结果: {resp.text}")
    except Exception as e:
        print(f"消息发送失败: {e}")

def check_and_notify():
    """主逻辑：分析天气并发送提醒"""
    global LAST_ALERT_DATE
    weather_data = get_weather_forecast()
    if not weather_data:
        send_wework_message("⚠️ 天气服务暂时无法访问，请稍后检查。")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 临时添加：打印今天的天气代码，用于调试
    daily_data = weather_data.get("daily", {})
    daily_weathercodes = daily_data.get("weathercode", [])
    daily_times = daily_data.get("time", [])
    
    for i, day_str in enumerate(daily_times):
        if day_str == today_str and i < len(daily_weathercodes):
            code = daily_weathercodes[i]
            print(f"【调试】今天的天气代码是: {code}")
            # 根据代码判断是否在 rain_codes 中
            if is_rain(code):
                print(f"【调试】代码 {code} 被判定为有雨")
            else:
                print(f"【调试】代码 {code} 被判定为无雨")
            break
    # 后面的原代码保持不变，继续...
    
    # 如果今天有雨，且今天还没有发过提醒，就发送消息
    if today_has_rain and LAST_ALERT_DATE.get("today") != today_str:
        msg = f"🌧️ {CITY_NAME}今天整体预报有雨，请及时将室外货物移至室内！"
        send_wework_message(msg)
        LAST_ALERT_DATE["today"] = today_str
    
    # 2. 检查明天是否有雨，并处理“明天”的提醒（下午5点左右触发）
    tomorrow_has_rain = False
    for i, day_str in enumerate(daily_times):
        if day_str == tomorrow_str and i < len(daily_weathercodes):
            if is_rain(daily_weathercodes[i]):
                tomorrow_has_rain = True
                break
    
    # 如果明天有雨，且明天还没有发过提醒，就发送消息
    if tomorrow_has_rain and LAST_ALERT_DATE.get("tomorrow") != tomorrow_str:
        msg = f"🌙 {CITY_NAME}明天预报有雨，请在下班前将室外货物移至室内！"
        send_wework_message(msg)
        LAST_ALERT_DATE["tomorrow"] = tomorrow_str

if __name__ == "__main__":
    check_and_notify()
