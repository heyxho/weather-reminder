import os
import requests
from datetime import datetime, timedelta

# ==================== 配置区 ====================
WEWORK_WEBHOOK = os.environ.get('WEWORK_WEBHOOK')
if not WEWORK_WEBHOOK:
    raise Exception("❌ 环境变量 WEWORK_WEBHOOK 未设置！")

LATITUDE = 36.389
LONGITUDE = 120.447
CITY_NAME = "青岛即墨区"

FORECAST_HOURS = 6          # 未来几小时提醒
TEST_MODE = False            # 测试模式改为 True 发送测试消息
# ===============================================

def get_beijing_time():
    """返回当前北京时间（UTC+8）"""
    return datetime.utcnow() + timedelta(hours=8)

def get_current_weather_and_forecast():
    """获取实时天气和逐小时预报（含降水量）"""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&current_weather=true"
        f"&hourly=weathercode,precipitation"
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
    """判断天气代码是否表示雨（包括毛毛雨、小雨、中雨、大雨、阵雨、雷暴）"""
    rain_codes = set(range(51, 58)) | set(range(61, 68)) | set(range(80, 83)) | {95, 96, 99}
    return weathercode in rain_codes

def get_weather_description(code):
    """天气代码转中文描述"""
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
    """发送消息到企业微信群，返回是否成功"""
    headers = {"Content-Type": "application/json"}
    payload = {"msgtype": "text", "text": {"content": content}}
    try:
        resp = requests.post(WEWORK_WEBHOOK, json=payload, headers=headers, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print(f"消息发送成功: {result}")
            return True
        else:
            print(f"消息发送失败: {result}")
            return False
    except Exception as e:
        print(f"消息发送异常: {e}")
        return False

def read_sent_flag(filename):
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def write_sent_flag(filename, date_str):
    with open(filename, 'w') as f:
        f.write(date_str)

def check_and_notify():
    def check_and_notify():
    # 临时清除缓存（运行一次后请删除这几行）
        import os
        for f in ["last_sent_today.txt", "last_sent_tomorrow.txt"]:
            try: os.remove(f); print(f"已删除 {f}")
            except FileNotFoundError: pass
    # 以下是原有代码...
    if TEST_MODE:
        print("测试模式：发送模拟提醒")
        title = "🌧️ 青岛即墨区 雨天提醒（测试）"
        body = "⚠️ 今日有降雨，各部门注意将室外货物移入室内！"
        weather_info = "📍 当前天气：晴（测试），22℃"
        tip = "温馨提示：雨天路滑，注意出行安全~"
        message = f"{title}\n\n{body}\n{weather_info}\n{tip}\n\n（测试消息，请确认能收到）"
        send_wework_message(message)
        return

    data = get_current_weather_and_forecast()
    if not data:
        send_wework_message("⚠️ 天气服务暂时无法访问，请稍后检查。")
        return

    # 当前天气
    current = data.get("current_weather", {})
    temp = current.get("temperature")
    weather_code = current.get("weathercode")
    current_desc = get_weather_description(weather_code) if weather_code is not None else "未知"

    # 逐小时数据
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    codes = hourly.get("weathercode", [])
    precipitations = hourly.get("precipitation", [])

    now_beijing = get_beijing_time()
    today_str = now_beijing.strftime("%Y-%m-%d")
    tomorrow_str = (now_beijing + timedelta(days=1)).strftime("%Y-%m-%d")

    # 读取已发送记录
    sent_today = read_sent_flag("last_sent_today.txt")
    sent_tomorrow = read_sent_flag("last_sent_tomorrow.txt")

    # 检查今天未来 FORECAST_HOURS 小时内是否有雨（降水量 > 0）
    rain_hours_today = []
    for i, t_str in enumerate(times):
        if i >= len(codes) or i >= len(precipitations):
            continue
        t = datetime.fromisoformat(t_str)
        if t >= now_beijing and t <= now_beijing + timedelta(hours=FORECAST_HOURS):
            if is_rain(codes[i]) and precipitations[i] > 0:
                rain_hours_today.append(t.strftime("%H:%M"))

    # 检查明天全天是否有雨（降水量 > 0）
    tomorrow_has_rain = False
    for i, t_str in enumerate(times):
        if i >= len(codes) or i >= len(precipitations):
            continue
        if t_str.startswith(tomorrow_str):
            if is_rain(codes[i]) and precipitations[i] > 0:
                tomorrow_has_rain = True
                break

    # 今日提醒
    if rain_hours_today and sent_today != today_str:
        hour_list = "、".join(rain_hours_today)
        title = "🌧️ 青岛即墨区 雨天提醒"
        body = "⚠️ 未来24小时有降雨，各部门注意将室外货物移入室内！"
        weather_info = f"📍 当前天气：{current_desc}，{temp}℃"
        tip = "温馨提示：雨天路滑，注意出行安全~"
        message = f"{title}\n\n{body}\n{weather_info}\n{tip}\n\n（预计未来{hour_list}左右降雨）"
        if send_wework_message(message):
            write_sent_flag("last_sent_today.txt", today_str)
            print("今日提醒已发送并记录缓存")
        else:
            print("今日提醒发送失败，未记录缓存，下次仍会尝试")
    elif rain_hours_today:
        print("今日已有发送记录，跳过")
    else:
        print("未来6小时无降雨")

    # 明日提醒
    if tomorrow_has_rain and sent_tomorrow != tomorrow_str:
        title = "🌧️ 青岛即墨区 雨天提醒"
        body = "⚠️ 明天有降雨，各部门请在下班前将室外货物移入室内！"
        weather_info = f"📍 当前天气：{current_desc}，{temp}℃"
        tip = "温馨提示：雨天路滑，注意出行安全~"
        message = f"{title}\n\n{body}\n{weather_info}\n{tip}"
        if send_wework_message(message):
            write_sent_flag("last_sent_tomorrow.txt", tomorrow_str)
            print("明日提醒已发送并记录缓存")
        else:
            print("明日提醒发送失败，未记录缓存，下次仍会尝试")
    elif tomorrow_has_rain:
        print("明天已有发送记录，跳过")
    else:
        print("明天无降雨")

if __name__ == "__main__":
    check_and_notify()
