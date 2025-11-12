import os
import base64
import json
from datetime import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydub import AudioSegment

app = FastAPI(title="Twilio Media Stream Demo")

SAVE_DIR = "received_audio"
os.makedirs(SAVE_DIR, exist_ok=True)


# ---------- 1️⃣ TwiML webhook ----------
@app.post("/answer")
async def answer_call(request: Request):
    print("executing updated answer section...")

    """
    Twilio hits this endpoint when a call comes in.
    It responds with TwiML telling Twilio to start a Media Stream
    to the /media WebSocket endpoint.
    """
    stream_url = os.getenv("STREAM_URL", "wss://twilio-media-stream-demo.onrender.com/media")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="wss://twilio-media-stream-demo.onrender.com/media" track="both_tracks" />
    </Start>
    <Say voice="Polly.Joanna">Hello, this is a FastAPI Twilio Media Stream demo. Please speak now.</Say>
    <Pause length="60"/>
</Response>"""

    return Response(content=twiml, media_type="text/xml")


# ---------- 2️⃣ WebSocket endpoint ----------
@app.websocket("/media")
async def media_stream(ws: WebSocket):
    """
    Twilio connects here and sends JSON messages containing
    base64 μ-law audio frames.
    """
    print("STarted websocket connection....")
    await ws.accept()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(SAVE_DIR, f"twilio_{ts}.raw")
    wav_path = os.path.join(SAVE_DIR, f"twilio_{ts}.wav")
    mp3_path = os.path.join(SAVE_DIR, f"twilio_{ts}.mp3")

    print("🔗 Twilio WebSocket connected")

    with open(raw_path, "wb") as f:
        try:
            while True:
                msg = await ws.receive_text()
                data = json.loads(msg)
                event = data.get("event")
                print("ws event data is...", event)

                if event == "start":
                    call_sid = data.get("start", {}).get("callSid")
                    print(f"▶️  Stream started for call: {call_sid}")

                elif event == "media":
                    payload = data["media"]["payload"]
                    chunk = base64.b64decode(payload)
                    f.write(chunk)

                elif event == "stop":
                    print("⏹️  Stream stopped.")
                    break

        except WebSocketDisconnect:
            print("❌ WebSocket disconnected.")
        except Exception as e:
            print("⚠️  Error:", e)

    print("Executing save audio script......")
    # Convert ULaw → WAV → MP3
    try:
        audio = AudioSegment.from_file(raw_path, format="ulaw", frame_rate=8000, channels=1)
        audio.export(wav_path, format="wav")
        audio.export(mp3_path, format="mp3")
        print(f"✅ Converted and saved as MP3: {mp3_path}")
    except Exception as e:
        print(f"⚠️ Error converting audio: {e}")


# ---------- 3️⃣ Root check ----------
@app.get("/")
def home():
    return {"status": "ok", "message": "Twilio Media Stream FastAPI server running."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
