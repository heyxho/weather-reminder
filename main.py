import os
import requests
from datetime import datetime, timedelta

# ==================== 配置区 ====================
LATITUDE = 36.389
LONGITUDE = 120.447
CITY_NAME = "青岛即墨区"
FORECAST_HOURS = 6
TEST_MODE = False
# ===============================================

def get_beijing_time():
    return datetime.utcnow() + timedelta(hours=8)

def get_weather_data():
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
        print(f"获取天气失败: {e}")
        return None

def is_rain(code):
    rain_codes = set(range(51, 58)) | set(range(61, 68)) | set(range(80, 83)) | {95, 96, 99}
    return code in rain_codes

def desc(code):
    m = {0:"晴",1:"晴",2:"多云",3:"阴",45:"雾",48:"雾",
         51:"毛毛雨",53:"毛毛雨",55:"毛毛雨",
         61:"小雨",63:"中雨",65:"大雨",
         80:"阵雨",81:"强阵雨",82:"大阵雨",95:"雷暴"}
    return m.get(code, "未知")

def send_msg(content):
    webhook = os.environ.get('WEWORK_WEBHOOK')
    if not webhook:
        print("⚠️ 未找到 WEWORK_WEBHOOK，跳过发送")
        return
    headers = {"Content-Type": "application/json"}
    payload = {"msgtype": "text", "text": {"content": content}}
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        print(f"发送结果: {resp.text}")
    except Exception as e:
        print(f"发送失败: {e}")

def check():
    data = get_weather_data()
    if not data:
        send_msg("⚠️ 天气服务异常")
        return

    # 当前天气
    cur = data.get("current_weather", {})
    temp = cur.get("temperature")
    cur_code = cur.get("weathercode")
    cur_desc = desc(cur_code)

    # 逐小时数据
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    codes = hourly.get("weathercode", [])
    precips = hourly.get("precipitation", [])

    now = get_beijing_time()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"当前天气: {cur_desc}, {temp}℃")
    print("\n========== 未来48小时逐小时预报 ==========")

    # 打印所有小时数据（方便查看明天凌晨）
    for i, t_str in enumerate(times):
        if i >= len(codes) or i >= len(precips):
            break
        t = datetime.fromisoformat(t_str)
        rain_flag = is_rain(codes[i])
        prec = precips[i]
        print(f"{t_str} 代码={codes[i]} 降水={prec}mm 是雨={rain_flag}")

    # 筛选今天未来6小时有雨的小时
    rain_hours_today = []
    for i, t_str in enumerate(times):
        if i >= len(codes) or i >= len(precips):
            continue
        t = datetime.fromisoformat(t_str)
        if t >= now and t <= now + timedelta(hours=FORECAST_HOURS):
            if is_rain(codes[i]) and precips[i] > 0.01:  # 阈值改为0.01mm
                rain_hours_today.append(t.strftime("%H:%M"))

    # 检查明天是否有雨（全天任意小时降水量 > 0.01mm）
    tomorrow_rain = False
    for i, t_str in enumerate(times):
        if i >= len(codes) or i >= len(precips):
            continue
        if t_str.startswith(tomorrow):
            if is_rain(codes[i]) and precips[i] > 0.01:
                tomorrow_rain = True
                break

    print(f"\n明天是否有雨（降水>0.01mm）: {tomorrow_rain}")
    print(f"今天未来{FORECAST_HOURS}小时有雨的小时: {rain_hours_today}")

    # 去重缓存
    try:
        with open("last_sent_today.txt") as f:
            sent_today = f.read().strip()
    except:
        sent_today = ""
    try:
        with open("last_sent_tomorrow.txt") as f:
            sent_tomorrow = f.read().strip()
    except:
        sent_tomorrow = ""

    # 今日提醒
    if rain_hours_today and sent_today != today:
        hour_str = "、".join(rain_hours_today)
        msg = f"🌧️ {CITY_NAME} 雨天提醒\n\n⚠️ 今日有降雨，请将室外货物移入室内！\n📍 当前天气：{cur_desc}，{temp}℃\n温馨提示：雨天路滑，注意安全~\n（预计 {hour_str} 左右降雨）"
        send_msg(msg)
        with open("last_sent_today.txt", "w") as f:
            f.write(today)
    elif rain_hours_today:
        print("今日已发送过提醒，跳过")
    else:
        print("未来6小时无有效降雨（降水量≤0.01mm）")

    # 明日提醒
    if tomorrow_rain and sent_tomorrow != tomorrow:
        msg = f"🌧️ {CITY_NAME} 雨天提醒\n\n⚠️ 明天有降雨，请在下班前将货物移入室内！\n📍 当前天气：{cur_desc}，{temp}℃\n温馨提示：雨天路滑，注意安全~"
        send_msg(msg)
        with open("last_sent_tomorrow.txt", "w") as f:
            f.write(tomorrow)
    elif tomorrow_rain:
        print("明天已发送过提醒，跳过")
    else:
        print("明天无有效降雨（降水量≤0.01mm）")

if __name__ == "__main__":
    check()
