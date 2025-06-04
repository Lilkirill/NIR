import os
from flask import Flask, request, jsonify
from pyfcm import FCMNotification
from datetime import datetime, timedelta
import openai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


push_service = FCMNotification(api_key=os.getenv("FIREBASE_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_checklist(event_type):
    prompt = f"""
    Сгенерируй детальный чек-лист для мероприятия типа "{event_type}".
    Включи задачи, которые нельзя забыть (например, бронь зала, приглашение гостей).
    Формат: "Задача | Дней до мероприятия".
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message["content"]


def send_reminder(device_token, task, due_date):
    message = {
        "title": "Напоминание",
        "body": f"{task} (до {due_date.strftime('%d.%m.%Y')})"
    }
    push_service.notify_single_device(
        registration_id=device_token,
        message_title=message["title"],
        message_body=message["body"],
        sound="default"
    )


@app.route("/schedule_event", methods=["POST"])
def schedule_event():
    data = request.json
    event_type = data["event_type"]
    device_token = data["device_token"]
    

    checklist_text = generate_checklist(event_type)
    

    tasks = []
    for line in checklist_text.split("\n"):
        if "|" in line:
            task, days = line.split("|")
            tasks.append({
                "task": task.strip(),
                "due_date": datetime.now() + timedelta(days=int(days.strip()))
            })
    

    for item in tasks:
        send_reminder(device_token, item["task"], item["due_date"])
    
    return jsonify({"status": "success", "checklist": checklist_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)