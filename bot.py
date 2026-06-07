import asyncio,json,logging,random,re
from datetime import datetime
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from aiogram import Bot,Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
BOT_TOKEN="8813248099:AAFFLIysH0ecogwe5DOpi3MsRqQc4oVMsbU"
CHAT_ID="777397042"
CHECK_URL="https://munich.pasport.org.ua/solutions/e-queue"
INTERVAL=600
SEEN_FILE=Path("seen_slots.json")
STATUS_FILE=Path("status.json")
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s",handlers=[logging.StreamHandler()])
log=logging.getLogger(__name__)
HEADERS={"User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"uk-UA,uk;q=0.9,ru;q=0.8","Accept-Encoding":"gzip, deflate, br","Connection":"keep-alive","Upgrade-Insecure-Requests":"1","Cache-Control":"max-age=0"}
def load_seen():
 if SEEN_FILE.exists():
  try:return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
  except:pass
 return set()
def save_seen(s):SEEN_FILE.write_text(json.dumps(sorted(s),ensure_ascii=False,indent=2),encoding="utf-8")
def save_status(s):STATUS_FILE.write_text(json.dumps(s,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
def load_status():
 if STATUS_FILE.exists():
  try:return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
  except:pass
 return{"last_check":None,"found":0,"new":0,"error":None}
async def fetch_slots():
 slots=[]
 await asyncio.sleep(random.uniform(2,6))
 try:
  async with httpx.AsyncClient(headers=HEADERS,timeout=30,follow_redirects=True) as c:
   r=await c.get(CHECK_URL);r.raise_for_status();html=r.text
  soup=BeautifulSoup(html,"html.parser")
  text=soup.get_text(separator=" ")
  tl=text.lower()
  no_kw=["немає вільних","нет свободных","no slots","талони відсутні","черга відсутня","немає доступних"]
  yes_kw=["записатися","зайняти чергу","доступно","вільний","free slot","available"]
  no_slots=any(k in tl for k in no_kw)
  has_slots=any(k in tl for k in yes_kw)
  log.info("has=%s no=%s",has_slots,no_slots)
  if has_slots and not no_slots:
   dates=re.findall(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}",text)
   times=re.findall(r"\d{1,2}:\d{2}",text)
   if dates:
    for i,d in enumerate(dates[:5]):
     t=times[i] if i<len(times) else "—"
     sid=re.sub(r"[^\w]","_",f"{d}_{t}")
     slots.append({"id":sid,"date":d,"time":t,"service":"Вільний талон","url":CHECK_URL})
   else:
    sid=f"alert_{datetime.now().strftime('%Y%m%d_%H')}"
    slots.append({"id":sid,"date":"Перевірте сайт","time":"Терміново!","service":"Знайдено вільні талони — заходьте зараз!","url":CHECK_URL})
 except httpx.HTTPStatusError as e:
  log.error("HTTP %s",e.response.status_code)
  if e.response.status_code==403:
   sid=f"check_{datetime.now().strftime('%Y%m%d_%H')}"
   slots.append({"id":sid,"date":"Невідомо","time":"Перевірте вручну","service":"Сайт потребує перевірки вручну — можливо є вільні місця!","url":CHECK_URL})
  else:raise
 except Exception as e:log.error("Err:%s",e);raise
 return slots
async def check_and_notify(bot):
 status={"last_check":datetime.now().strftime("%d.%m.%Y %H:%M:%S"),"found":0,"new":0,"error":None}
 try:
  slots=await fetch_slots();status["found"]=len(slots)
  seen=load_seen();new=[s for s in slots if s["id"] not in seen];status["new"]=len(new)
  for s in new:
   await bot.send_message(chat_id=CHAT_ID,text=f"🟢 *Знайдено вільний талон!*\n\n📅 *Дата:* {s['date']}\n🕐 *Час:* {s['time']}\n📋 {s['service']}\n\n🔗 [Записатися зараз]({s['url']})\n\n_{status['last_check']}_",parse_mode="Markdown")
   seen.add(s["id"]);log.info("Notified:%s",s["id"])
  if len(seen)>1000:seen=set(sorted(seen)[-1000:])
  save_seen(seen)
 except Exception as e:status["error"]=str(e);log.error("Error:%s",e)
 save_status(status);return status
async def scheduler(bot):
 while True:
  await asyncio.sleep(max(60,INTERVAL+random.uniform(-90,90)))
  await check_and_notify(bot)
dp=Dispatcher()
@dp.message(Command("start"))
async def cmd_start(m:Message):await m.answer(f"👋 *Бот моніторингу консульства Мюнхен*\n\n🌐 {CHECK_URL}\n⏱ Кожні {INTERVAL//60} хв\n\n/check — перевірити зараз\n/status — статус",parse_mode="Markdown")
@dp.message(Command("check"))
async def cmd_check(m:Message,bot:Bot):
 await m.answer("🔍 Перевіряю...")
 s=await check_and_notify(bot)
 if s.get("error"):await m.answer(f"❌ `{s['error']}`",parse_mode="Markdown")
 elif s["new"]>0:await m.answer(f"✅ Надіслано *{s['new']}* нових слотів!",parse_mode="Markdown")
 elif s["found"]>0:await m.answer("ℹ️ Слоти вже надсилались раніше.")
 else:await m.answer(f"😔 Вільних талонів не знайдено.\n{CHECK_URL}")
@dp.message(Command("status"))
async def cmd_status(m:Message):
 s=load_status()
 await m.answer(f"📊 *Статус*\n\n🕐 `{s.get('last_check') or 'не виконувалась'}`\n🔍 Знайдено: *{s.get('found',0)}*\n🆕 Надіслано: *{s.get('new',0)}*\n{'❌ '+s['error'] if s.get('error') else '✅ Помилок немає'}",parse_mode="Markdown")
async def main():
 bot=Bot(token=BOT_TOKEN)
 try:await bot.send_message(chat_id=CHAT_ID,text=f"🚀 *Бот запущено!*\n\n🌐 {CHECK_URL}\n⏱ Кожні {INTERVAL//60} хв\n\n/check — перевірити зараз",parse_mode="Markdown")
 except Exception as e:log.warning("Startup:%s",e)
 await asyncio.gather(dp.start_polling(bot,allowed_updates=["message"]),scheduler(bot))
if __name__=="__main__":asyncio.run(main())
