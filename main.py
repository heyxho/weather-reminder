import requests
from datetime import datetime, timedelta

# ==================== 配置区 ====================
# 请替换为你的企业微信群机器人 Webhook 地址
WEWORK_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"

# 青岛即墨的坐标（高德坐标系，Open-Meteo 使用 WGS84，直接可用）
LATITUDE = 36.389
LONGITUDE = 120.447
CITY_NAME = "青岛即墨区"

# 未来多少小时内下雨算“即将下雨”
FORECAST_HOURS = 6

# 降水概率阈值（%），高于此值才认为会下雨（避免极小概率误报）
PROBABILITY_THRESHOLD = 30
# ===============================================

def get_current_weather_and_forecast():
    """
    获取当前天气（温度、天气状况）和未来逐小时预报（含降水概率）
    使用 Open-Meteo API
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&current_weather=true"
        f"&hourly=weathercode,precipitation_probability"
        f"&daily=weathercode"
        f"&timezone=Asia/Shanghai"
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
    """判断天气代码是否表示任何形式的雨（包括小雨、中雨、大雨、毛毛雨、阵雨、雷暴）"""
    rain_codes = set(range(51, 58)) | set(range(61, 68)) | set(range(80, 83)) | {95, 96, 99}
    return weathercode in rain_codes

def get_weather_description(code):
    """将天气代码转为中文描述（仅用于当前天气）"""
    # 参考：https://open-meteo.com/en/docs
    weather_map = {
        0: "晴",
        1: "晴",
        2: "局部多云",
        3: "阴",
        45: "雾",
        48: "雾",
        51: "毛毛雨",
        53: "毛毛雨",
        55: "毛毛雨",
        56: "冻毛毛雨",
        57: "冻毛毛雨",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        66: "冻雨",
        67: "强冻雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        77: "雪粒",
        80: "阵雨",
        81: "强阵雨",
        82: "大阵雨",
        85: "阵雪",
        86: "强阵雪",
        95: "雷暴",
        96: "雷暴伴小冰雹",
        99: "雷暴伴大冰雹",
    }
    return weather_map.get(code, "未知")

def send_wework_message(content):
    """发送消息到企业微信群"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "text",
        "text": {
            "content": content,
            # "mentioned_list": ["@all"]   # 如需@所有人，取消注释
        }
    }
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

    # 1. 获取当前天气
    current = data.get("current_weather", {})
    temp = current.get("temperature")
    weather_code = current.get("weathercode")
    current_desc = get_weather_description(weather_code) if weather_code is not None else "未知"

    # 2. 获取逐小时数据
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    codes = hourly.get("weathercode", [])
    probs = hourly.get("precipitation_probability", [])

    now = datetime.now()
    rain_hours_today = []
    tomorrow_has_rain = False
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    for i, t_str in enumerate(times):
        if i >= len(codes) or i >= len(probs):
            continue
        t = datetime.fromisoformat(t_str)
        # 未来 FORECAST_HOURS 小时内的降雨（今日）
        if t >= now and t <= now + timedelta(hours=FORECAST_HOURS):
            if is_rain(codes[i]) and probs[i] >= PROBABILITY_THRESHOLD:
                rain_hours_today.append(t.strftime("%H:%M"))
        # 检查明天是否有雨
        if t_str.startswith(tomorrow_str):
            if is_rain(codes[i]) and probs[i] >= PROBABILITY_THRESHOLD:
                tomorrow_has_rain = True

    # 3. 准备消息内容
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
