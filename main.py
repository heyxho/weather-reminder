import requests
from datetime import datetime, timedelta, timezone

# ==================== 配置区 ====================
WEWORK_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fa2dde06-bf5e-499c-9aaa-548eb085cb24"

LATITUDE = 36.389
LONGITUDE = 120.447
CITY_NAME = "青岛即墨区"

FORECAST_HOURS = 6
PROBABILITY_THRESHOLD = 50   # 降水概率阈值，可调整为 40、50、60
# ===============================================

def get_beijing_time():
    """获取当前北京时间（UTC+8）"""
    # GitHub Actions 服务器是 UTC 时间，加 8 小时得到北京时间
    utc_now = datetime.utcnow()
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now

def get_current_weather_and_forecast():
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&current_weather=true"
        f"&hourly=weathercode,precipitation_probability"
        f"&daily=weathercode"
        f"&timezone=Asia/Shanghai"          # API 返回北京时间
        f"&forecast_days=2"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"获取天气数据失败: {e}")
        return None

def is_rain(weathercode):
    rain_codes = set(range(51, 58)) | set(range(61, 68)) | set(range(80, 83)) | {95, 96, 99}
    return weathercode in rain_codes

def get_weather_description(code):
    weather_map = {
        0: "晴", 1: "晴", 2: "局部多云", 3: "阴",
        45: "雾", 48: "雾",
        51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
        56: "冻毛毛雨", 57: "冻毛毛雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        66: "冻雨", 67: "强冻雨",
        71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
        80: "阵雨", 81: "强阵雨", 82: "大阵雨",
        85: "阵雪", 86: "强阵雪",
        95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
    }
    return weather_map.get(code, "未知")

def send_wework_message(content):
    headers = {"Content-Type": "application/json"}
    payload = {"msgtype": "text", "text": {"content": content}}
    try:
        resp = requests.post(WEWORK_WEBHOOK, json=payload, headers=headers, timeout=10)
        print(f"消息发送结果: {resp.text}")
        return resp.status_code == 200
    except Exception as e:
        print(f"消息发送失败: {e}")
        return False

def check_and_notify():
    data = get_current_weather_and_forecast()
    if not data:
        send_wework_message("⚠️ 天气服务暂时无法访问，请稍后检查。")
        return

    # 当前天气（API 返回的 current_weather 里的时间也是北京时间）
    current = data.get("current_weather", {})
    temp = current.get("temperature")
    weather_code = current.get("weathercode")
    current_desc = get_weather_description(weather_code) if weather_code is not None else "未知"

    # 逐小时数据（时间字符串已经是北京时间）
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    codes = hourly.get("weathercode", [])
    probs = hourly.get("precipitation_probability", [])

    now_beijing = get_beijing_time()
    rain_hours_today = []
    tomorrow_has_rain = False
    tomorrow_str = (now_beijing + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"当前北京时间: {now_beijing}")
    print(f"未来 {FORECAST_HOURS} 小时内的逐小时预报：")

    for i, t_str in enumerate(times):
        if i >= len(codes) or i >= len(probs):
            continue
        # 解析 API 返回的时间字符串（格式如 "2026-04-20T15:00"）
        t = datetime.fromisoformat(t_str)
        # 只关注未来 FORECAST_HOURS 小时内
        if t >= now_beijing and t <= now_beijing + timedelta(hours=FORECAST_HOURS):
            is_rain_flag = is_rain(codes[i])
            prob = probs[i]
            print(f"  {t_str}: 代码={codes[i]}, 降水概率={prob}%, 是否为雨={is_rain_flag}")
            if is_rain_flag and prob >= PROBABILITY_THRESHOLD:
                rain_hours_today.append(t.strftime("%H:%M"))
        # 检查明天是否有雨（全天任意小时）
        if t_str.startswith(tomorrow_str):
            if is_rain(codes[i]) and probs[i] >= PROBABILITY_THRESHOLD:
                tomorrow_has_rain = True

    # 发送消息
    if rain_hours_today:
        hour_list = "、".join(rain_hours_today)
        title = "🌧️ 青岛即墨区 雨天提醒"
        body = "⚠️ 今日有降雨，各部门注意将室外货物移入室内！"
        weather_info = f"📍 当前天气：{current_desc}，{temp}℃"
        tip = "温馨提示：雨天路滑，注意出行安全~"
        message = f"{title}\n\n{body}\n{weather_info}\n{tip}\n\n（预计未来{hour_list}左右降雨）"
        send_wework_message(message)
    elif tomorrow_has_rain:
        title = "🌧️ 青岛即墨区 雨天提醒"
        body = "⚠️ 明天有降雨，各部门请在下班前将室外货物移入室内！"
        weather_info = f"📍 当前天气：{current_desc}，{temp}℃"
        tip = "温馨提示：雨天路滑，注意出行安全~"
        message = f"{title}\n\n{body}\n{weather_info}\n{tip}"
        send_wework_message(message)
    else:
        print("未来一天无高概率降雨，无需提醒")

if __name__ == "__main__":
    check_and_notify()
