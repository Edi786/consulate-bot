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
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s",handlers=[logging.StreamHandler(),logging.FileHandler("bot.log",encoding="utf-8")])
log=logging.getLogger(__name__)
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36","Accept-Language":"uk-UA,uk;q=0.9"}
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
 await asyncio.sleep(random.uniform(1,5))
 try:
  async with httpx.AsyncClient(headers=HEADERS,timeout=30,follow_redirects=True) as c:
   r=await c.get(CHECK_URL);r.raise_for_status();html=r.text
  soup=BeautifulSoup(html,"html.parser")
  page_text=soup.get_text(separator=" ").lower()
  keywords=["записатися","зайняти","доступно","вільно","записаться","available"]
  has_slots=any(k in page_text for k in keywords)
  els=(soup.select(".queue-item")+soup.select(".slot-item")+soup.select(".available-slot")+soup.select(".time-slot")+soup.select("[class*='queue']")+soup.select("[class*='slot']")+soup.select("li.item")+soup.select(".card-body"))
  for el in els:
   text=el.get_text(separator=" ").strip()
   if not text or len(text)<4:continue
   dm=re.search(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}",text)
   tm=re.search(r"\d{1,2}:\d{2}",text)
   if not dm and not tm:continue
   sid=re.sub(r"[^\w]","_",f"{dm.group() if dm else ''}_{tm.group() if tm else ''}_{text[:30]}")
   slots.append({"id":sid,"date":dm.group() if dm else "Дивіться сайт","time":tm.group() if tm else "Дивіться сайт","service":text[:100],"url":CHECK_URL})
  if not slots and has_slots:
   slots.append({"id":f"general_{datetime.now().strftime('%Y%m%d')}","date":"Перевірте сайт","time":"Перевірте сайт","service":"Знайдено ознаки вільних талонів","url":CHECK_URL})
  log.info("Slots:%d has_slots:%s",len(slots),has_slots)
 except Exception as e:log.error("Fetch error:%s",e);raise
 return slots
async def check_and_notify(bot):
 status={"last_check":datetime.now().strftime("%d.%m.%Y %H:%M:%S"),"found":0,"new":0,"error":None}
 try:
  slots=await fetch_slots();status["found"]=len(slots)
  seen=load_seen();new=[s for s in slots if s["id"] not in seen];status["new"]=len(new)
  for s in new:
   await bot.send_message(chat_id=CHAT_ID,text=f"🟢 *Знайдено вільний талон!*\n\n📅 *Дата:* {s['date']}\n🕐 *Час:* {s['time']}\n📋 {s['service'][:150]}\n\n🔗 [Записатися]({s['url']})\n\n_{status['last_check']}_",parse_mode="Markdown")
   seen.add(s["id"]);log.info("Notified:%s",s["id"])
  if len(seen)>1000:seen=set(sorted(seen)[-1000:])
  save_seen(seen)
 except Exception as e:status["error"]=str(e);log.error("Error:%s",e)
 save_status(status);return status
async def scheduler(bot):
 log.info("Scheduler started %d min",INTERVAL//60)
 while True:
  await asyncio.sleep(max(60,INTERVAL+random.uniform(-90,90)))
  log.info("Checking...")
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
 log.info("Bot starting...")
 try:await bot.send_message(chat_id=CHAT_ID,text=f"🚀 *Бот запущено!*\n\n🌐 {CHECK_URL}\n⏱ Кожні {INTERVAL//60} хв\n\n/check — перевірити зараз",parse_mode="Markdown")
 except Exception as e:log.warning("Startup msg failed:%s",e)
 await asyncio.gather(dp.start_polling(bot,allowed_updates=["message"]),scheduler(bot))
if __name__=="__main__":asyncio.run(main())
